
import logging
import os
import time

import mitogen.core
import mitogen.master


LOG = logging.getLogger(__name__)
PASSWORD_PROMPT = 'password'


class PasswordError(mitogen.core.Error):
    pass


class Stream(mitogen.master.Stream):
    create_child = staticmethod(mitogen.master.tty_create_child)
    sudo_path = 'sudo'
    password = None

    def construct(self, username=None, sudo_path=None, password=None, **kwargs):
        """
        Get the named sudo context, creating it if it does not exist.

        :param mitogen.core.Broker broker:
            The broker that will own the context.

        :param str username:
            Username to pass to sudo as the ``-u`` parameter, defaults to ``root``.

        :param str sudo_path:
            Filename or complete path to the sudo binary. ``PATH`` will be searched
            if given as a filename. Defaults to ``sudo``.

        :param str python_path:
            Filename or complete path to the Python binary. ``PATH`` will be
            searched if given as a filename. Defaults to :py:data:`sys.executable`.

        :param str password:
            The password to use when authenticating to sudo. Depending on the sudo
            configuration, this is either the current account password or the
            target account password. :py:class:`mitogen.sudo.PasswordError` will
            be raised if sudo requests a password but none is provided.

        """
        super(Stream, self).construct(**kwargs)
        self.username = username or 'root'
        if sudo_path:
            self.sudo_path = sudo_path
        if password:
            self.password = password
        self.name = 'sudo.' + self.username

    def get_boot_command(self):
        bits = [self.sudo_path, '-u', self.username]
        bits = bits + super(Stream, self).get_boot_command()
        LOG.debug('sudo command line: %r', bits)
        return bits

    password_incorrect_msg = 'sudo password is incorrect'
    password_required_msg = 'sudo password is required'

    def _connect_bootstrap(self):
        password_sent = False
        for buf in mitogen.master.iter_read(self.receive_side.fd,
                                             time.time() + 10.0):
            LOG.debug('%r: received %r', self, buf)
            if buf.endswith('EC0\n'):
                return self._ec0_received()
            elif PASSWORD_PROMPT in buf.lower():
                if self.password is None:
                    raise PasswordError(self.password_required_msg)
                if password_sent:
                    raise PasswordError(self.password_incorrect_msg)
                LOG.debug('sending password')
                os.write(self.transmit_side.fd, self.password + '\n')
                password_sent = True
        else:
            raise mitogen.core.StreamError('bootstrap failed')
