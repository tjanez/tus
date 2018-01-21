from setuptools import find_packages, setup

setup(
    name='tus',
    version='0.1',
    packages=['tus'],
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'tus-par2 = tus.par2:cli',
            'tus-partclone = tus.partclone:cli',
            'tus-sessionstore = tus.sessionstore_geturls:main'
        ],
    },
)
