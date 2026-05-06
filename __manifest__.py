{
    'name': 'correos-leads',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Gestión de correos para leads inmobiliarios',
    'description': """
        Modulo para la gestion y seguimiento de correos electronicos asociados a leads inmobiliarios
    """,
    'author': 'ia-prop.com',
    'website': 'https://ia-prop.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/correos_leads_views.xml',
    ],
    'demo': [],
    'assets': {},
    'installable': True,
    'application': True,
    'auto_install': False,
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
}
