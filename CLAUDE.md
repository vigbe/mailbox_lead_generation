# CLAUDE.md - correos-leads

> **ARCHIVO DE MEMORIA CLAUDE** - Documentacion tecnica para asistentes AI
>
> Este modulo es para **Odoo 19 Community Edition**.

---

## Informacion del Modulo

| Campo | Valor |
|-------|-------|
| **Nombre** | correos-leads |
| **Modelo** | `correos.leads` |
| **Clase** | `CorreosLeads` |
| **Version** | `19.0.1.0.0` |
| **Dependencias** | base |

---

## Estructura

```
correos_leads/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── models/
│   ├── __init__.py
│   └── correos_leads.py
├── security/
│   ├── ir.model.access.csv
│   └── security_groups.xml
├── views/
│   └── correos_leads_views.xml
└── tests/
    ├── __init__.py
    └── test_module.py
```

---

## Reglas Odoo 19 (CRITICO)

### DEBE usar
- `<list>` (NO `<tree>`)
- Atributos directos: `invisible="..."`, `readonly="..."`, `required="..."`
- `@api.ondelete(at_uninstall=False)` para validacion de eliminacion
- `@api.model_create_multi` para `create()`
- `from odoo.fields import Command` para operaciones relacionales
- `store=True` en campos computados consultados frecuentemente
- `self.ensure_one()` en metodos de accion

### NUNCA usar
- `attrs` (deprecated)
- `<tree>` (usar `<list>`)
- `cr.commit()` manual
- jQuery (solo OWL)

---

## Referencias

- **Skill Odoo 19**: `.agents/skills/odoo-19/SKILL.md`
- **Guias detalladas**: `.agents/skills/odoo-19/dev/`
- **Odoo 19 Docs**: https://github.com/odoo/documentation/tree/19.0

---

*Documentacion actualizada para Odoo 19 - correos-leads*
