from setuptools import setup

setup(
    name='scrapy-magicfields',
    version='1.0.0',
    license='BSD',
    description='Scrapy middleware to add extra "magic" fields to items',
    author='Scrapinghub',
    author_email='info@scrapinghub.com',
    url='http://github.com/scrapy-plugins/scrapy-magicfields',
    packages=['scrapy_magicfields'],
    platforms=['Any'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    install_requires=['scrapy']
)
