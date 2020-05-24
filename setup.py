#!/usr/bin/env python
# coding: utf-8

from setuptools import find_packages, setup


if __name__ == '__main__':
    setup(
        name='aiohttp-rpc',
        version='0.1.0',
        author='Michael Sulyak',
        url='https://github.com/expert-m/aiohttp-rpc/',
        author_email='michael@sulyak.info',
        keywords=(
            'aiohttp', 'asyncio', 'json-rpc',
        ),
        install_requires=(
            'aiohttp>=3,<4',
        ),
        license='MIT license',
        python_requires='>=3.5',
        packages=find_packages(),
        classifiers=(
            # 'Development Status :: 1 - Planning',
            # 'Development Status :: 2 - Pre-Alpha',
            'Development Status :: 3 - Alpha',
            # 'Development Status :: 4 - Beta',
            # 'Development Status :: 5 - Production/Stable',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Operating System :: OS Independent',
            'Programming Language :: Python :: 3',
            'Topic :: Software Development :: Libraries :: Python Modules',
        ),
    )
