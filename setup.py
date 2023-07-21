#!/usr/bin/env python
# coding: utf-8

from setuptools import find_packages, setup


def main() -> None:
    with open('README.md') as file:
        long_description = file.read()

    packages = find_packages(exclude=['tests'])
    package_data = {package: ['py.typed'] for package in packages}

    setup(
        name='aiohttp-rpc',
        version='1.3.0',
        author='Michael Sulyak',
        url='https://github.com/expert-m/aiohttp-rpc/',
        author_email='michael@sulyak.info',
        keywords=[
            'aiohttp', 'asyncio', 'json-rpc', 'rpc',
        ],
        install_requires=[
            'aiohttp>=3,<4',
        ],
        license='MIT license',
        description='A simple JSON-RPC for aiohttp',
        long_description=long_description,
        long_description_content_type='text/markdown',
        python_requires='>=3.7',
        packages=packages,
        package_data=package_data,
        classifiers=[
            # 'Development Status :: 1 - Planning',
            # 'Development Status :: 2 - Pre-Alpha',
            # 'Development Status :: 3 - Alpha',
            # 'Development Status :: 4 - Beta',
            'Development Status :: 5 - Production/Stable',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
            'Framework :: AsyncIO',
            'Framework :: aiohttp',
            'Topic :: Internet',
            'Topic :: Communications',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: Libraries :: Python Modules',
        ],
        project_urls={
            'GitHub: issues': 'https://github.com/expert-m/aiohttp-rpc/issues',
            'GitHub: repo': 'https://github.com/expert-m/aiohttp-rpc',
        },
    )


if __name__ == '__main__':
    main()
