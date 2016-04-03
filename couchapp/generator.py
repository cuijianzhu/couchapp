# -*- coding: utf-8 -*-
#
# This file is part of couchapp released under the Apache 2 license.
# See the NOTICE for more information.

from __future__ import with_statement

import logging
import os
import shutil
import sys

from couchapp.errors import AppError
from couchapp import localdoc
from couchapp.util import is_py2exe, is_windows, relpath, setup_dir, user_path

__all__ = ["init_basic", "init_template", "generate_function", "generate"]

logger = logging.getLogger(__name__)


DEFAULT_APP_TREE = ['_attachments',
                    'lists',
                    'shows',
                    'updates',
                    'views']


def init_basic(path):
    '''
    Generate a basic CouchApp which contain following files::

        /path/
            .couchapprc
            .couchappignore
            _attachments/
            lists/
            shows/
            updates/
            views/
    '''
    setup_dir(path, require_empty=True)

    for n in DEFAULT_APP_TREE:
        tp = os.path.join(path, n)
        os.makedirs(tp)

    fid = os.path.join(path, '_id')
    if not os.path.isfile(fid):
        with open(fid, 'wb') as f:
            f.write('_design/{0}'.format(os.path.split(path)[1]))

    localdoc.document(path, create=True)


def init_template(path, template=None):
    '''
    Generates a CouchApp via template
    '''
    TEMPLATES = ['app']
    prefix = os.path.join(*template.split('/')) if template is not None else ''

    setup_dir(path, require_empty=True)

    for n in DEFAULT_APP_TREE:
        tp = os.path.join(path, n)
        os.makedirs(tp)

    for t in TEMPLATES:
        appdir = path
        if prefix:
            # we do the job twice for now to make sure an app or vendor
            # template exist in user template location
            # fast on linux since there is only one user dir location
            # but could be a little slower on windows
            for user_location in user_path():
                location = os.path.join(user_location, 'templates', prefix, t)
                if os.path.exists(location):
                    t = os.path.join(prefix, t)
                    break

        copy_helper(appdir, t)

    # add vendor
    vendor_dir = os.path.join(appdir, 'vendor')
    os.makedirs(vendor_dir)
    copy_helper(vendor_dir, '', tname="vendor")

    fid = os.path.join(appdir, '_id')
    if not os.path.isfile(fid):
        with open(fid, 'wb') as f:
            f.write('_design/{0}'.format(os.path.split(appdir)[1]))

    localdoc.document(path, create=True)


def generate_function(path, kind, name, template=None):
    functions_path = ['functions']
    if template:
        functions_path = []
        _relpath = os.path.join(*template.split('/'))
        template_dir = find_template_dir("templates", _relpath)
    else:
        template_dir = find_template_dir("templates")
    if template_dir:
        functions = []
        if kind == "view":
            path = os.path.join(path, "%ss" % kind, name)
            if os.path.exists(path):
                raise AppError("The view %s already exists" % name)
            functions = [('map.js', 'map.js'), ('reduce.js', 'reduce.js')]
        elif kind == "function":
            functions = [('%s.js' % name, '%s.js' % name)]
        elif kind == "vendor":
            app_dir = os.path.join(path, "vendor", name)
            try:
                os.makedirs(app_dir)
            except:
                pass
            targetpath = os.path.join(*template.split('/'))
            copy_helper(path, targetpath)
            return
        elif kind == "spatial":
            path = os.path.join(path, "spatial")
            functions = [("spatial.js", "%s.js" % name)]
        else:
            path = os.path.join(path, "%ss" % kind)
            functions = [('%s.js' % kind, "%s.js" % name)]
        try:
            os.makedirs(path)
        except:
            pass

        for template, target in functions:
            target_path = os.path.join(path, target)
            root_path = [template_dir] + functions_path + [template]
            root = os.path.join(*root_path)
            try:
                shutil.copy2(root, target_path)
            except:
                logger.warning("%s not found in %s" %
                               (template, os.path.join(*root_path[:-1])))
    else:
        raise AppError("Defaults templates not found. Check your install.")


def copy_helper(path, directory, tname="templates"):
    """ copy helper used to generate an app"""
    if tname == "vendor":
        tname = os.path.join("templates", tname)

    templatedir = find_template_dir(tname, directory)
    if templatedir:
        if directory == "vendor":
            path = os.path.join(path, directory)
            try:
                os.makedirs(path)
            except:
                pass

        for root, dirs, files in os.walk(templatedir):
            rel = relpath(root, templatedir)
            if rel == ".":
                rel = ""
            target_path = os.path.join(path, rel)
            for d in dirs:
                try:
                    os.makedirs(os.path.join(target_path, d))
                except:
                    continue
            for f in files:
                shutil.copy2(os.path.join(root, f),
                             os.path.join(target_path, f))
    else:
        raise AppError(
            "Can't create a CouchApp in %s: default template not found." %
            (path))


def find_template_dir(name, directory=''):
    paths = ['%s' % name, os.path.join('..', name)]
    if is_py2exe():
        modpath = sys.executable
    elif is_windows():
        modpath = os.path.join(sys.prefix, "Lib", "site-packages", "couchapp",
                               "templates")
    else:
        modpath = __file__

    if not is_windows():
        default_locations = [
            "/usr/share/couchapp/templates/%s" % directory,
            "/usr/local/share/couchapp/templates/%s" % directory,
            "/opt/couchapp/templates/%s" % directory]

    else:
        default_locations = []

    default_locations.extend([os.path.join(os.path.dirname(modpath), p,
                                           directory) for p in paths])

    if sys.platform == "darwin":
        home = os.path.expanduser('~'),
        data_path = "%s/Library/Application Support/Couchapp" % home
        default_locations.extend(["%s/%s/%s" % (data_path, p, directory)
                                  for p in paths])

    if directory:
        for user_location in user_path():
            default_locations.append(os.path.join(user_location, name,
                                                  directory))

    found = False
    for location in default_locations:
        template_dir = os.path.normpath(location)
        if os.path.isdir(template_dir):
            found = True
            break
    if found:
        return template_dir
    return False


def generate(path, kind, name, **opts):
    if kind not in ['view', 'list', 'show', 'filter',
                    'function', 'vendor', 'update', 'spatial']:
        raise AppError("Can't generate {0} in your couchapp. "
                       'generator is unknown'.format(kind))

    if name is None:
        raise AppError("Can't generate {0} function, "
                       "name is missing".format(kind))

    generate_function(path, kind, name, opts.get("template"))
