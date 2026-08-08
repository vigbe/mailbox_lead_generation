# CLAUDE.md - Mail Box Lead Generation

> **ARCHIVO DE MEMORIA CLAUDE** - Documentacion tecnica para asistentes AI
>
> Este modulo es para **Odoo 19 Community Edition**.

---

## Informacion del Modulo

| Campo | Valor |
|-------|-------|
| **Nombre** | Mail Box Lead Generation |
| **Modelo** | `mailbox.lead.generation` |
| **Clase** | `MailboxLeadGeneration` |
| **Carpeta técnica** | `mailbox_lead_generation` |
| **Version** | `19.0.1.0.0` |
| **Dependencias** | base, crm, real_estate_products |

---

## Estructura

```
mailbox_lead_generation/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── models/
│   ├── __init__.py
│   ├── mailbox_lead_generation.py
│   └── res_config_settings.py
├── security/
│   ├── ir.model.access.csv
│   └── security_groups.xml
├── views/
│   └── mailbox_lead_generation_views.xml
└── tests/
    ├── __init__.py
    └── test_mailbox_lead_generation.py
```

---

## Config parameters (ir.config_parameter)

Todos usan el prefijo `mailbox_lead_generation.`:

| Clave | Campo settings | Uso |
|-------|----------------|-----|
| `mailbox_lead_generation.email_consultas` | `mailbox_email_consultas` | Direcciones clasificadas como "consulta" |
| `mailbox_lead_generation.email_captacion` | `mailbox_email_captacion` | Direcciones clasificadas como "captación" |
| `mailbox_lead_generation.ai_provider` | `mailbox_ai_provider` | Proveedor OpenAI-compatible |
| `mailbox_lead_generation.ai_api_key` | `mailbox_ai_api_key` | API key del proveedor |
| `mailbox_lead_generation.ai_model` | `mailbox_ai_model` | Modelo a invocar |
| `mailbox_lead_generation.ai_base_url` | `mailbox_ai_base_url` | Endpoint base |
| `mailbox_lead_generation.dynamic_model` | `mailbox_dynamic_model` | Modelo de matching (default: product.real_estate) |

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
- **Odoo 19 Docs**: <https://github.com/odoo/documentation/tree/19.0>

---

*Documentacion actualizada para Odoo 19 - Mail Box Lead Generation (antes correos-leads)*
