"""Package setup script."""
import setuptools

setuptools.setup(
    name='pi-stream',
    version='0.1',
    packages=setuptools.find_packages('src'),
    # package_data={},
    package_dir={'': 'src'},
    install_requires=[],
    extras_require={},
    setup_requires=[],
    tests_require=[],
)
