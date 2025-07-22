from setuptools import find_packages, setup

setup(
    name='netbox-tools',
    version='0.2.0',
    description='A NetBox plugin providing network-related tools like device lists without primary IPs.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='you@example.com',
    url='https://github.com/your-username/netbox-tools',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[],
    classifiers=[
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.10',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: System :: Networking',
    ],
)
