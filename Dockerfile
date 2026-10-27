FROM odoo:17.0

USER root
#RUN cat /etc/apt/sources.list
#RUN sed -i 's/stable\/updates/stable-security\/updates/' /etc/apt/sources.list
RUN mkdir -p /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo/sessions
RUN mkdir -p /mnt/utils /mnt/bundle-addons \
    && chown -R odoo:odoo /mnt/utils /mnt/bundle-addons

RUN apt-get update \
    && apt-get install -y  \
        vim \
        libtool \
        nginx \
        sudo \
        pkg-config \
        python3-dev \
        libffi-dev \
        python3 \
		#python3.8-dev  \
        #python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY ./odoo/extra-requirements.txt /mnt/utils/extra-requirements.txt
RUN export PIP_DEFAULT_TIMEOUT=1000000
RUN pip3 install -U wheel setuptools==58.0.0
RUN pip3 install -r /mnt/utils/extra-requirements.txt
RUN python3 - <<'PY'
from pathlib import Path
import ast
import pprint

path = Path('/usr/lib/python3/dist-packages/odoo/addons/base_setup/__manifest__.py')
data = ast.literal_eval(path.read_text())
if 'assets' not in data:
    data['assets'] = {}
    path.write_text(
        "# Patched during image build for Odoo 17 asset pipeline compatibility.\n"
        + pprint.pformat(data, sort_dicts=False)
        + "\n"
    )
PY
RUN python3 - <<'PY'
from pathlib import Path

path = Path('/usr/lib/python3/dist-packages/odoo/addons/base/models/ir_asset.py')
text = path.read_text()
old = "for command in odoo.modules.module._get_manifest_cached(addon)['assets'].get(bundle, ()):"
new = "for command in odoo.modules.module._get_manifest_cached(addon).get('assets', {}).get(bundle, ()):"
if old in text:
    text = text.replace(old, new)
    path.write_text(text)
PY

COPY ./odoo/scripts /mnt/utils/scripts
COPY ./odoo/conf /mnt/utils/scripts/conf
# COPY ./odoo/wait-for-it.sh /wait-for-it.sh

COPY ./external/ /mnt/bundle-addons/
COPY ./addons/ /mnt/bundle-addons/

COPY ./odoo/conf/web/nginx.conf /etc/nginx/nginx.conf
COPY ./odoo/conf/web/odoo.conf /etc/nginx/conf.d/default.conf


COPY ./odoo/entrypoint.sh /entrypoint.sh


# CMD ["run"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["run"]

