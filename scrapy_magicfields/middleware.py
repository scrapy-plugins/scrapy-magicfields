"""
Allow to add extra fields to items, based on the configuration setting MAGIC_FIELDS and MAGIC_FIELDS_OVERRIDE.
Both settings are a dict. The keys are the destination field names, their values, a string which admits magic variables,
identified by a starting '$', which will be substituted by a corresponding value. Some magic also accept arguments, and are specified
after the magic name, using a ':' as separator.

You can set project global magics with MAGIC_FIELDS, and tune them for a specific spider using MAGIC_FIELDS_OVERRIDE.

In case there is more than one argument, they must come separated by ','. So, the generic magic format is

$<magic name>[:arg1,arg2,...]

Current magic variables are:
    - $time
            The UTC timestamp at which the item was scraped, in format '%Y-%m-%d %H:%M:%S'.
    - $unixtime
            The unixtime (number of seconds since the Epoch, i.e. time.time()) at which the item was scraped.
    - $isotime
            The UTC timestamp at which the item was scraped, with format '%Y-%m-%dT%H:%M:%S".
    - $spider
            Must be followed by an argument, which is the name of an attribute of the spider (like an argument passed to it).
    - $env
            The value of an environment variable. It admits as argument the name of the variable.
    - $jobid
            The job id (shortcut for $env:SCRAPY_JOB)
    - $jobtime
            The UTC timestamp at which the job started, in format '%Y-%m-%d %H:%M:%S'.
    - $response
            Access to some response properties.
                $response:url
                    The url from where the item was extracted from.
                $response:status
                    Response http status.
                $response:headers
                    Response http headers.
    - $setting
            Access the given Scrapy setting. It accepts one argument: the name of the setting.
    - $field
            Allows to copy the value of one field to another. Its argument is the source field. Effects are unpredicable if you use as source a field that is filled
            using magic fields.

Examples:

The following configuration will add two fields to each scraped item: 'timestamp', which will be filled with the string 'item scraped at <scraped timestamp>',
and 'spider', which will contain the spider name:

MAGIC_FIELDS = {"timestamp": "item scraped at $time", "spider": "$spider:name"}

The following configuration will copy the url to the field sku:

MAGIC_FIELDS = {"sku": "$field:url"}

Magics admits also regular expression argument which allow to extract and assign only part of the value generated by the magic. You have to specify
it using the r'' notation. Suppose that the urls of your items are like 'http://www.example.com/product.html?item_no=345' and you want to assign to the sku field
only the item number. The following example, similar to the previous one but with a second regular expression argument, will do the task:

MAGIC_FIELDS = {"sku": "$field:url,r'item_no=(\d+)'"}

"""
import datetime
import os
import re
import time

from scrapy.exceptions import NotConfigured
from scrapy.item import BaseItem


def _time():
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def _isotime():
    return datetime.datetime.utcnow().isoformat()


_REGEXES = {}
_REGEX_ERRORS = {}
def _extract_regex_group(regex, txt):
    compiled = _REGEXES.get(regex)
    errmessage = _REGEX_ERRORS.get(regex)
    if compiled is None and errmessage is None:
        try:
            compiled = re.compile(regex)
            _REGEXES[regex] = compiled
        except Exception, e:
            errmessage = e.message
            _REGEX_ERRORS[regex] = errmessage
    if errmessage:
        raise ValueError(errmessage)
    m = compiled.search(txt)
    if m:
        return "".join(m.groups()) or None

_ENTITY_FUNCTION_MAP = {
    '$time': _time,
    '$unixtime': time.time,
    '$isotime': _isotime,
}

_ENTITIES_RE = re.compile("(\$[a-z]+)(:\w+)?(?:,r\'(.+)\')?")
def _first_arg(args):
    if args:
        return args.pop(0)


def _format(fmt, spider, response, item, fixed_values):
    out = fmt
    for m in _ENTITIES_RE.finditer(fmt):
        val = None
        entity, args, regex = m.groups()
        args = filter(None, (args or ':')[1:].split(','))
        if entity == "$jobid":
            val = os.environ.get('SCRAPY_JOB', '')
        elif entity == "$spider":
            attr = _first_arg(args)
            if not attr or not hasattr(spider, attr):
                spider.log("Error at '%s': spider does not have attribute" % m.group())
            else:
                val = str(getattr(spider, attr))
        elif entity == "$response":
            attr = _first_arg(args)
            if not attr or not hasattr(response, attr):
                spider.log("Error at '%s': response does not have attribute" % m.group())
            else:
                val = str(getattr(response, attr))
        elif entity == "$field":
            attr = _first_arg(args)
            if attr in item:
                val = str(item[attr])
        elif entity in fixed_values:
            attr = _first_arg(args)
            val = fixed_values[entity]
            if entity == "$setting" and attr:
                val = str(val[attr])
        elif entity == "$env" and args:
            attr = _first_arg(args)
            if attr:
                val = os.environ.get(attr, '')
        else:
            function = _ENTITY_FUNCTION_MAP.get(entity)
            if function is not None:
                try:
                    val = str(function(*args))
                except:
                    spider.log("Error at '%s': invalid argument for function" % m.group())
        if val is not None:
            out = out.replace(m.group(), val, 1)
        if regex:
            try:
                out = _extract_regex_group(regex, out)
            except ValueError, e:
                spider.log("Error at '%s': %s" % (m.group(), e.message))

    return out


class MagicFieldsMiddleware(object):

    @classmethod
    def from_crawler(cls, crawler):
        mfields = crawler.settings.getdict("MAGIC_FIELDS").copy()
        mfields.update(crawler.settings.getdict("MAGIC_FIELDS_OVERRIDE"))
        if not mfields:
            raise NotConfigured
        return cls(mfields, crawler.settings)

    def __init__(self, mfields, settings):
        self.mfields = mfields
        self.fixed_values = {
            "$jobtime": _time(),
            "$setting": settings,
        }

    def process_spider_output(self, response, result, spider):
        for _res in result:
            if isinstance(_res, BaseItem):
                for field, fmt in self.mfields.items():
                    _res.setdefault(field, _format(fmt, spider, response, _res, self.fixed_values))
            yield _res
