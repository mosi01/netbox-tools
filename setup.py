from setuptools import find_packages, setup

setup(
    name='netbox-tools',
    version='0.2',
    description='A NetBox plugin for helpful network tools.',
    url='https://github.com/mosi01/netbox-tools',
    author='Simon Möller Ahlquist',
    author_email='simon.moller@lindab.com',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
