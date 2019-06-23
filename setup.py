from setuptools import setup, find_packages

setup(
    name='yalla',
    version='0.2.0',
    packages=find_packages('src', exclude=['docs', 'tests']),
    package_dir={'': 'src'},
    url='',
    license='MIT',
    author='turu',
    author_email='',
    description='',
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
)
