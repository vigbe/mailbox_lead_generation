#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Architecture Control Agent
==========================

Agente de validación arquitectónica para módulos Odoo.
Valida:
- Dependencias circulares
- Violaciones de dominio
- Campos compute peligrosos
- Record rules riesgosas
- Cambios breaking en manifest

Uso:
    python architecture_control_agent.py [--module MODULE_PATH] [--all]
"""

import os
import re
import ast
import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Niveles de severidad para los hallazgos."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Finding:
    """Representa un hallazgo de la validación."""
    severity: Severity
    category: str
    message: str
    file: str = ""
    line: int = 0
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Resultado de la validación de un módulo."""
    module_name: str
    findings: List[Finding] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return any(f.severity in (Severity.ERROR, Severity.CRITICAL) for f in self.findings)
    
    @property
    def has_warnings(self) -> bool:
        return any(f.severity == Severity.WARNING for f in self.findings)


class ArchitectureControlAgent:
    """
    Agente de control de arquitectura para módulos Odoo.
    """
    
    # Patrones de campos compute peligrosos
    DANGEROUS_COMPUTE_PATTERNS = [
        r'@api\.depends\([^)]*,[^)]*,[^)]*,[^)]*\)',  # Más de 3 dependencias
        r'\.search\(',  # Búsquedas en compute
        r'\.browse\(',  # Browse en compute
        r'self\.env\[',  # Acceso a otros modelos
    ]
    
    # Campos que típicamente son peligrosos si son compute
    RISKY_FIELD_NAMES = [
        'image', 'kanban_image', 'thumbnail',  # Procesamiento de imágenes
        'total', 'amount', 'balance',  # Cálculos financieros
        'count', 'quantity',  # Conteos
    ]
    
    # Patrones de record rules riesgosas
    RISKY_RULE_PATTERNS = [
        r'\(1,\s*=,\s*1\)',  # Siempre verdadero
        r'\[\]',  # Dominio vacío
        r'user\.id',  # Acceso directo a user.id sin validación
    ]
    
    def __init__(self, module_path: str):
        self.module_path = Path(module_path)
        self.module_name = self.module_path.name
        self.manifest: Dict[str, Any] = {}
        self.models: Dict[str, Dict] = {}
        self.findings: List[Finding] = []
        
    def load_manifest(self) -> bool:
        """Carga el manifest del módulo."""
        manifest_path = self.module_path / '__manifest__.py'
        if not manifest_path.exists():
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category="manifest",
                message="No se encontró __manifest__.py",
                file=str(manifest_path)
            ))
            return False
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.manifest = ast.literal_eval(content)
            return True
        except Exception as e:
            self.findings.append(Finding(
                severity=Severity.CRITICAL,
                category="manifest",
                message=f"Error al parsear manifest: {e}",
                file=str(manifest_path)
            ))
            return False
    
    def validate_circular_dependencies(self, all_modules: Dict[str, List[str]]) -> None:
        """
        Valida que no existan dependencias circulares.
        
        Args:
            all_modules: Dict con nombre de módulo -> lista de dependencias
        """
        def find_cycle(module: str, visited: Set[str], path: List[str]) -> Optional[List[str]]:
            if module in path:
                cycle_start = path.index(module)
                return path[cycle_start:] + [module]
            
            if module in visited:
                return None
            
            visited.add(module)
            path.append(module)
            
            for dep in all_modules.get(module, []):
                if dep in all_modules:  # Solo verificar módulos locales
                    cycle = find_cycle(dep, visited, path)
                    if cycle:
                        return cycle
            
            path.pop()
            return None
        
        for module in all_modules:
            cycle = find_cycle(module, set(), [])
            if cycle:
                self.findings.append(Finding(
                    severity=Severity.CRITICAL,
                    category="dependencies",
                    message=f"Dependencia circular detectada: {' -> '.join(cycle)}",
                    suggestion="Refactorizar para eliminar la dependencia circular"
                ))
                break
    
    def validate_domain_violations(self) -> None:
        """Valida violaciones de dominio en el módulo."""
        models_path = self.module_path / 'models'
        if not models_path.exists():
            return
        
        # Detectar accesos a modelos de otros dominios
        domain_prefixes = {
            'ml.': 'mercado_libre',
            'rental.': 'rental_contracts',
            'real_estate.': 'real_estate',
            'project.': 'project',
            'crm.': 'crm',
        }
        
        module_domain = None
        for prefix, domain in domain_prefixes.items():
            if domain in self.module_name:
                module_domain = prefix
                break
        
        for py_file in models_path.glob('*.py'):
            if py_file.name == '__init__.py':
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Buscar accesos a self.env['modelo']
                env_accesses = re.findall(r"self\.env\['([^']+)'\]", content)
                
                for model in env_accesses:
                    for prefix, domain in domain_prefixes.items():
                        if model.startswith(prefix) and module_domain and prefix != module_domain:
                            # Verificar si es una dependencia declarada
                            if domain not in str(self.manifest.get('depends', [])):
                                self.findings.append(Finding(
                                    severity=Severity.WARNING,
                                    category="domain_violation",
                                    message=f"Acceso a modelo '{model}' de otro dominio sin dependencia declarada",
                                    file=str(py_file),
                                    suggestion=f"Agregar '{domain}' a las dependencias o usar una interfaz"
                                ))
            except Exception as e:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category="parse_error",
                    message=f"Error al analizar {py_file.name}: {e}",
                    file=str(py_file)
                ))
    
    def validate_dangerous_compute_fields(self) -> None:
        """Valida campos compute potencialmente peligrosos."""
        models_path = self.module_path / 'models'
        if not models_path.exists():
            return
        
        for py_file in models_path.glob('*.py'):
            if py_file.name == '__init__.py':
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Buscar campos compute
                compute_pattern = r"(\w+)\s*=\s*fields\.\w+\([^)]*compute\s*="
                
                for i, line in enumerate(lines, 1):
                    match = re.search(compute_pattern, line)
                    if match:
                        field_name = match.group(1)
                        
                        # Verificar si es un campo riesgoso
                        for risky_name in self.RISKY_FIELD_NAMES:
                            if risky_name in field_name.lower():
                                self.findings.append(Finding(
                                    severity=Severity.WARNING,
                                    category="dangerous_compute",
                                    message=f"Campo compute '{field_name}' puede ser costoso",
                                    file=str(py_file),
                                    line=i,
                                    suggestion="Considerar usar store=True o optimizar el cálculo"
                                ))
                                break
                
                # Buscar patrones peligrosos en métodos compute
                for pattern in self.DANGEROUS_COMPUTE_PATTERNS:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        self.findings.append(Finding(
                            severity=Severity.INFO,
                            category="compute_pattern",
                            message=f"Patrón potencialmente costoso en compute: {match.group()[:50]}...",
                            file=str(py_file),
                            line=line_num
                        ))
                        
            except Exception as e:
                pass  # Ya manejado en validate_domain_violations
    
    def validate_record_rules(self) -> None:
        """Valida record rules potencialmente riesgosas."""
        security_path = self.module_path / 'security'
        if not security_path.exists():
            return
        
        for xml_file in security_path.glob('*.xml'):
            try:
                with open(xml_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Buscar record rules
                rule_pattern = r'<record[^>]*model="ir\.rule"[^>]*>.*?</record>'
                rules = re.findall(rule_pattern, content, re.DOTALL)
                
                for rule in rules:
                    # Buscar el dominio
                    domain_match = re.search(r'name="domain_force"[^>]*>([^<]+)<', rule)
                    if domain_match:
                        domain = domain_match.group(1)
                        
                        for pattern in self.RISKY_RULE_PATTERNS:
                            if re.search(pattern, domain):
                                self.findings.append(Finding(
                                    severity=Severity.WARNING,
                                    category="risky_rule",
                                    message=f"Record rule con patrón riesgoso: {domain[:100]}...",
                                    file=str(xml_file),
                                    suggestion="Revisar la regla de seguridad"
                                ))
                                
            except Exception as e:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category="parse_error",
                    message=f"Error al analizar {xml_file.name}: {e}",
                    file=str(xml_file)
                ))
    
    def validate_manifest_breaking_changes(self) -> None:
        """Valida cambios potencialmente breaking en el manifest."""
        if not self.manifest:
            return
        
        # Verificar archivos comentados en data
        data_files = self.manifest.get('data', [])
        commented_count = 0
        
        manifest_path = self.module_path / '__manifest__.py'
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Contar líneas comentadas en la sección data
            commented_count = len(re.findall(r"#\s*'[^']+\.xml'", content))
            
            if commented_count > 3:
                self.findings.append(Finding(
                    severity=Severity.WARNING,
                    category="manifest_breaking",
                    message=f"Hay {commented_count} archivos comentados en el manifest",
                    file=str(manifest_path),
                    suggestion="Limpiar archivos comentados o documentar por qué están deshabilitados"
                ))
        except Exception:
            pass
        
        # Verificar dependencias externas opcionales
        external_deps = self.manifest.get('external_dependencies', {})
        python_deps = external_deps.get('python', [])
        
        if python_deps:
            self.findings.append(Finding(
                severity=Severity.INFO,
                category="external_deps",
                message=f"Dependencias Python externas: {', '.join(python_deps)}",
                file=str(manifest_path),
                suggestion="Asegurar que las dependencias estén instaladas en producción"
            ))
        
        # Verificar hooks
        hooks = ['pre_init_hook', 'post_init_hook', 'uninstall_hook', 'post_upgrade_hook']
        for hook in hooks:
            if hook in self.manifest:
                self.findings.append(Finding(
                    severity=Severity.INFO,
                    category="hooks",
                    message=f"Hook definido: {hook} = {self.manifest[hook]}",
                    file=str(manifest_path)
                ))
    
    def validate_hardcoded_ids(self) -> None:
        """Detecta IDs hardcodeados en el código."""
        models_path = self.module_path / 'models'
        if not models_path.exists():
            return
        
        # Patrones de IDs hardcodeados
        id_patterns = [
            r'\b\d+:\s*\d+\b',  # Mapeos como 1: 1
            r"\.browse\(\d+\)",  # browse con ID fijo
            r"\.search\([^)]*\('id',\s*'=',\s*\d+\)",  # search con ID fijo
        ]
        
        for py_file in models_path.glob('*.py'):
            if py_file.name == '__init__.py':
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    # Ignorar comentarios
                    if line.strip().startswith('#'):
                        continue
                    
                    for pattern in id_patterns:
                        if re.search(pattern, line):
                            self.findings.append(Finding(
                                severity=Severity.WARNING,
                                category="hardcoded_id",
                                message=f"Posible ID hardcodeado: {line.strip()[:80]}...",
                                file=str(py_file),
                                line=i,
                                suggestion="Usar XML IDs o configuración en lugar de IDs numéricos"
                            ))
                            break
                            
            except Exception:
                pass
    
    def run_validation(self) -> ValidationResult:
        """Ejecuta todas las validaciones."""
        if not self.load_manifest():
            return ValidationResult(self.module_name, self.findings)
        
        self.validate_domain_violations()
        self.validate_dangerous_compute_fields()
        self.validate_record_rules()
        self.validate_manifest_breaking_changes()
        self.validate_hardcoded_ids()
        
        return ValidationResult(self.module_name, self.findings)
    
    def generate_report(self, result: ValidationResult) -> str:
        """Genera un reporte de la validación."""
        lines = [
            "=" * 80,
            f"ARCHITECTURE CONTROL REPORT: {result.module_name}",
            "=" * 80,
            "",
        ]
        
        if not result.findings:
            lines.append("✅ No se encontraron problemas.")
        else:
            # Agrupar por severidad
            by_severity = {}
            for finding in result.findings:
                sev = finding.severity.value
                if sev not in by_severity:
                    by_severity[sev] = []
                by_severity[sev].append(finding)
            
            # Mostrar en orden de severidad
            for severity in ['CRITICAL', 'ERROR', 'WARNING', 'INFO']:
                if severity in by_severity:
                    lines.append(f"\n{'🔴' if severity in ('CRITICAL', 'ERROR') else '🟡' if severity == 'WARNING' else 'ℹ️'} {severity}:")
                    lines.append("-" * 40)
                    
                    for finding in by_severity[severity]:
                        lines.append(f"  [{finding.category}] {finding.message}")
                        if finding.file:
                            lines.append(f"    📁 {finding.file}" + (f":{finding.line}" if finding.line else ""))
                        if finding.suggestion:
                            lines.append(f"    💡 {finding.suggestion}")
                        lines.append("")
        
        lines.append("=" * 80)
        
        # Resumen
        total = len(result.findings)
        critical = sum(1 for f in result.findings if f.severity == Severity.CRITICAL)
        errors = sum(1 for f in result.findings if f.severity == Severity.ERROR)
        warnings = sum(1 for f in result.findings if f.severity == Severity.WARNING)
        info = sum(1 for f in result.findings if f.severity == Severity.INFO)
        
        lines.append(f"RESUMEN: {total} hallazgos ({critical} críticos, {errors} errores, {warnings} warnings, {info} info)")
        lines.append("=" * 80)
        
        return "\n".join(lines)


def find_all_modules(base_path: Path) -> Dict[str, List[str]]:
    """Encuentra todos los módulos Odoo y sus dependencias."""
    modules = {}
    
    for item in base_path.iterdir():
        if item.is_dir():
            manifest_path = item / '__manifest__.py'
            if manifest_path.exists():
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = ast.literal_eval(f.read())
                    modules[item.name] = manifest.get('depends', [])
                except Exception:
                    pass
    
    return modules


def main():
    parser = argparse.ArgumentParser(description='Architecture Control Agent para módulos Odoo')
    parser.add_argument('--module', '-m', help='Ruta al módulo a validar')
    parser.add_argument('--all', '-a', action='store_true', help='Validar todos los módulos en el directorio actual')
    parser.add_argument('--output', '-o', help='Archivo de salida para el reporte')
    
    args = parser.parse_args()
    
    if args.all:
        base_path = Path('.')
        all_modules = find_all_modules(base_path)
        
        reports = []
        for module_name in all_modules:
            module_path = base_path / module_name
            agent = ArchitectureControlAgent(str(module_path))
            
            # Validar dependencias circulares
            agent.validate_circular_dependencies(all_modules)
            
            result = agent.run_validation()
            reports.append(agent.generate_report(result))
        
        full_report = "\n\n".join(reports)
        
    elif args.module:
        agent = ArchitectureControlAgent(args.module)
        
        # Buscar otros módulos para validar dependencias circulares
        base_path = Path(args.module).parent
        all_modules = find_all_modules(base_path)
        agent.validate_circular_dependencies(all_modules)
        
        result = agent.run_validation()
        full_report = agent.generate_report(result)
        
    else:
        parser.print_help()
        return
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(full_report)
        print(f"Reporte guardado en: {args.output}")
    else:
        print(full_report)


if __name__ == '__main__':
    main()
