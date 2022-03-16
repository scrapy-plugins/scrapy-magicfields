import datetime
import logging
import os
import re
import time

from scrapy.exceptions import NotConfigured
from scrapy.item import Item as BaseItem


logger = logging.getLogger(__name__)


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
        except Exception as e:
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
        args = list(filter(None, (args or ':')[1:].split(',')))
        if entity == "$jobid":
            val = os.environ.get('SCRAPY_JOB', '')
        elif entity == "$spider":
            attr = _first_arg(args)
            if not attr or not hasattr(spider, attr):
                logger.warning("Error at '%s': spider does not have attribute" % m.group())
            else:
                val = str(getattr(spider, attr))
        elif entity == "$response":
            attr = _first_arg(args)
            if not attr or not hasattr(response, attr):
                logger.warning("Error at '%s': response does not have attribute" % m.group())
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
                    logger.warning("Error at '%s': invalid argument for function" % m.group())
        if val is not None:
            out = out.replace(m.group(), val, 1)
        if regex:
            try:
                out = _extract_regex_group(regex, out)
            except ValueError as e:
                logger.warning("Error at '%s': %s" % (m.group(), e.message))

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
            if isinstance(_res, (BaseItem, dict)):
                for field, fmt in self.mfields.items():
                    _res.setdefault(field, _format(fmt, spider, response, _res, self.fixed_values))
            yield _res

