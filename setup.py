from setuptools import setup, find_packages

setup(
    name='yalal',
    version='0.3.0',
    packages=find_packages('src', exclude=['docs', 'tests']),
    package_dir={'': 'src'},
    url='https://github.com/turu/yalal',
    license='MIT',
    author='Piotr Turek',
    author_email='piotr.turu.turek@gmail.com',
    description="Yet Another Lame Algorithm Library of algorithms and data structures used in machine learning "
                "and large scale data processing, implemented from scratch for fun and (no) profit",
    setup_requires=["pytest-runner"],
    tests_require=["pytest"],
)
