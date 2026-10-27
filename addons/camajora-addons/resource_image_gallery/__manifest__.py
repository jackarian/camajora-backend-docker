# Copyright 2018 Akretion (http://www.akretion.com).
# @author Raphaël Reverdy <https://github.com/hparfr>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Resource Image Gallery",
    "summary": "Link images to rental resources",
    'version': '17.0.1.0',
    'license': 'AGPL-3',
    'author': 'Metadonors srl',
    'website': 'https://www.metadonors.it',
    "depends": ["fs_base_multi_image", "rental_api"],
    "data": [
        "security/ir.model.access.csv",
        "views/resource_image_relation.xml",
        "views/rental_resource.xml",
        "views/image_tag.xml",
        "views/fs_image.xml",
    ],
    "assets": {},
}
