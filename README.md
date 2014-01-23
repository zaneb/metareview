Metareview
==========

This is a tool to aid in reviewing Gerrit reviewers by listing out all of their reviews on a project.

By default the project is `openstack/heat` on `review.openstack.org`, but you can modify it by passing the `--project` and `--ssh-server` flags on the command line.

Usage
-----

    Usage: metareview.py [-p PROJECT] [-u SSH_USER] [-s SSH_SERVER] REVIEWER

    A tool for reviewing reviewers.  Prints all of the comments left by a given
    Gerrit reviewer.  By Zane Bitter <zbitter@redhat.com>

    Options:
      -h, --help            show this help message and exit
      -p PROJECT, --project=PROJECT
                            The project to look in. Defaults to "openstack/heat".
      -u SSH_USER, --ssh-user=SSH_USER
                            The Gerrit username to connect with.
      -s SSH_SERVER, --ssh-server=SSH_SERVER
                            The Gerrit server to connect to. Defaults to
                            "review.openstack.org".

License
-------

This software is licensed under the Apache License, Version 2.0. Please see the `LICENSE` file for details.
