# Odoo 19 Documentation - AI Agents Setup

Setup guide for using Odoo 19 documentation with AI coding assistants (Cursor, Claude Code, OpenCode, etc.).

## Quick Start

### Remote Repository (Recommended)

**Cursor IDE** - Configure once:
- `Settings` → `Rules` → `Add Remote Rule`
- Source: `Git Repository`
- URL: `git@github.com:unclecatvn/agent-skills.git`
- Branch: `odoo/19.0`
- Subfolder: `agent-skills/skills/odoo/19.0/`

### Local Copy

```bash
# Clone repository
git clone git@github.com:unclecatvn/agent-skills.git

# Copy to your project
cp -r agent-skills/skills/odoo/19.0 /your-project/agent-skills/skills/odoo/

# For Claude Code, create symlink
ln -s agent-skills/skills/odoo/19.0/CLAUDE.md ./CLAUDE.md
```

---

## Documentation Structure

```
agent-skills/skills/odoo/19.0/
├── SKILL.md                       # Master index (all agents)
├── dev/                           # Development guides folder (19 files)
│   ├── odoo-19-actions-guide.md     # ir.actions.*, cron, bindings
│   ├── odoo-19-controller-guide.md  # HTTP, routing, controllers
│   ├── odoo-19-data-guide.md        # XML/CSV data files, records
│   ├── odoo-19-decorator-guide.md   # @api decorators
│   ├── odoo-19-development-guide.md # Manifest, wizards (overview)
│   ├── odoo-19-field-guide.md       # Field types, parameters
│   ├── odoo-19-manifest-guide.md    # __manifest__.py reference
│   ├── odoo-19-mixins-guide.md      # mail.thread, activities, etc.
│   ├── odoo-19-model-guide.md       # ORM, CRUD, search, domain
│   ├── odoo-19-migration-guide.md   # Migration scripts, hooks
│   ├── odoo-19-owl-guide.md         # OWL components, services
│   ├── odoo-19-performance-guide.md # N+1 prevention, optimization
│   ├── odoo-19-reports-guide.md     # QWeb reports, PDF/HTML
│   ├── odoo-19-security-guide.md    # ACL, record rules, security
│   ├── odoo-19-testing-guide.md     # Test classes, decorators
│   ├── odoo-19-transaction-guide.md # Savepoints, errors
│   ├── odoo-19-translation-guide.md # Translations, i18n
│   └── odoo-19-view-guide.md        # XML views, QWeb
├── CLAUDE.md                      # Claude Code specific
└── AGENTS.md                      # THIS FILE - setup guide
```

---

## Guide Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `SKILL.md` | Master index for all guides | Find the right guide for your task |
| `dev/odoo-19-actions-guide.md` | Actions (window, URL, server, cron) | Creating actions, menus, scheduled jobs |
| `dev/odoo-19-controller-guide.md` | HTTP controllers, routing | Writing endpoints |
| `dev/odoo-19-data-guide.md` | XML/CSV data files, records | Creating data files |
| `dev/odoo-19-decorator-guide.md` | @api decorators usage | Using @api decorators |
| `dev/odoo-19-development-guide.md` | Module structure, wizards | Creating new modules |
| `dev/odoo-19-field-guide.md` | Field types, parameters | Defining model fields |
| `dev/odoo-19-manifest-guide.md` | __manifest__.py reference | Configuring module manifest |
| `dev/odoo-19-mixins-guide.md` | mail.thread, activities, mixins | Adding messaging, activities |
| `dev/odoo-19-model-guide.md` | ORM methods, CRUD, domains | Writing model methods |
| `dev/odoo-19-migration-guide.md` | Migration scripts, hooks | Upgrading modules |
| `dev/odoo-19-owl-guide.md` | OWL components, hooks, services | Building OWL UI |
| `dev/odoo-19-performance-guide.md` | Performance optimization | Fixing slow code |
| `dev/odoo-19-reports-guide.md` | QWeb reports, templates | Creating reports |
| `dev/odoo-19-security-guide.md` | ACL, record rules, security | Configuring security |
| `dev/odoo-19-testing-guide.md` | Test classes, decorators, mocking | Writing tests |
| `dev/odoo-19-transaction-guide.md` | Database transactions, error handling | Savepoints, UniqueViolation |
| `dev/odoo-19-translation-guide.md` | Translations, localization, i18n | Adding translations |
| `dev/odoo-19-view-guide.md` | XML views, actions, menus | Writing view XML |

---

## AI Agent Configuration

### Cursor IDE

| Setting | Value |
|---------|-------|
| Source | Git Repository |
| URL | `git@github.com:unclecatvn/agent-skills.git` |
| Branch | `odoo/19.0` |
| Subfolder | `agent-skills/skills/odoo/19.0/` |

**Globs patterns used by Cursor:**

| File | globs Pattern |
|------|---------------|
| `SKILL.md` | `**/*.{py,xml}` |
| `dev/odoo-19-actions-guide.md` | `**/*.{py,xml}` |
| `dev/odoo-19-controller-guide.md` | `**/controllers/**/*.py` |
| `dev/odoo-19-data-guide.md` | `**/*.{xml,csv}` |
| `dev/odoo-19-decorator-guide.md` | `**/models/**/*.py` |
| `dev/odoo-19-development-guide.md` | `**/*.{py,xml,csv}` |
| `dev/odoo-19-field-guide.md` | `**/models/**/*.py` |
| `dev/odoo-19-manifest-guide.md` | `**/__manifest__.py` |
| `dev/odoo-19-mixins-guide.md` | `**/models/**/*.py` |
| `dev/odoo-19-model-guide.md` | `**/models/**/*.py` |
| `dev/odoo-19-migration-guide.md` | `**/migrations/**/*.py` |
| `dev/odoo-19-owl-guide.md` | `static/src/**/*.{js,xml}` |
| `dev/odoo-19-performance-guide.md` | `**/*.{py,xml}` |
| `dev/odoo-19-reports-guide.md` | `**/report/**/*.xml` |
| `dev/odoo-19-security-guide.md` | `**/security/**/*.{csv,xml}` |
| `dev/odoo-19-testing-guide.md` | `**/tests/**/*.py` |
| `dev/odoo-19-transaction-guide.md` | `**/models/**/*.py` |
| `dev/odoo-19-translation-guide.md` | `**/*.{py,js,xml}` |
| `dev/odoo-19-view-guide.md` | `**/views/**/*.xml` |

### Claude Code

```bash
# Place CLAUDE.md in project root
ln -s agent-skills/skills/odoo/19.0/CLAUDE.md ./CLAUDE.md
```

Claude Code reads:
- `CLAUDE.md` - Project overview and quick reference
- `SKILL.md` - Master index for all guides
- Individual guides in `dev/` - Detailed information

### OpenCode

Copy documentation to project - no additional configuration needed.

### Other Agents

| Agent | Setup |
|-------|-------|
| Windsurf | Same as Cursor (uses `.mdc` files) |
| Continue | Place `CLAUDE.md` or `dev/SKILL.md` in root |
| Aider | Place `CLAUDE.md` or add to prompt |

---

## Cursor / Claude Skills Folder

For Cursor IDE with local rules, create:

```
.cursor/skills/
└── odoo-19/
    └── SKILL.md -> ../../agent-skills/skills/odoo/19.0/SKILL.md
```

Or for Claude Code:

```
.claude/skills/
└── odoo-19/
    └── SKILL.md -> ../../agent-skills/skills/odoo/19.0/SKILL.md
```

### Key Odoo 19 Changes

| Change | Old | New |
|--------|-----|-----|
| List view tag | `<tree>` | `<list>` |
| Dynamic attributes | `attrs="{'invisible': [...]}"` | `invisible="..."` |
| Delete validation | Override `unlink()` | `@api.ondelete(at_uninstall=False)` |
| Field aggregation | `group_operator=` | `aggregator=` |

---

## Repository

**URL**: `git@github.com:unclecatvn/agent-skills.git`

**License**: MIT
