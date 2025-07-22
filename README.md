# netbox-tools
A utility plugin for NetBox providing helpful views, tools, and insights — such as listing devices missing primary IPs — to simplify network data hygiene and operations.

✨ Features

🔍 View devices without a primary IP address

🧰 Extendable structure for additional tools

🔒 Uses NetBox's permission framework

🧩 Seamless integration with the NetBox UI




📦 Installation

Clone into your plugins directory:

cd /opt/netbox/netbox/plugins/
git clone https://github.com/YOUR_ORG/netbox-tools.git

Install the plugin in the NetBox virtual environment:

cd /opt/netbox/netbox/plugins/netbox-tools
pip install -e .

Add the plugin to configuration.py:

PLUGINS = [
    ...,
    'netbox_tools',
]

Restart NetBox services:

sudo systemctl restart netbox netbox-rq
sudo nginx -s reload




🧪 Usage

Once installed, a new menu labeled "NetBox Tools" will appear in the top navigation. It includes tools such as:

Devices without Primary IP – Lists devices missing primary IPv4/IPv6 addresses




🖼️ Screenshots

(Insert screenshots here of the plugin menu and views.)




🛠️ Development

To modify or add tools:

Extend views under netbox_tools/views/

Register them in urls.py

Update the navigation menu in navigation.py

After changes:

pip install -e .
python3 manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq




🧾 License



🙋‍♂️ Questions or Issues?

Open a GitHub Issue or start a Discussion!




✅ TODO

