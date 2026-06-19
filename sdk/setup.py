from setuptools import setup, find_packages

setup(
    name="kimchi-sdk",
    version="0.4.0",
    description="Python SDK for the Kimchi MLOps Model Registry",
    author="Shivam Upadhyay",
    packages=find_packages(),
    install_requires=["requests>=2.28.0"],
    python_requires=">=3.10",
)
