from setuptools import setup

setup(
    name='tus',
    version='0.1',
    py_modules=['par2'],
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'tus-par2 = par2:cli',
        ],
    },
)
