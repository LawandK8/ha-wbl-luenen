import socket
import sys

import aiohttp
import pytest
import pytest_socket

if sys.platform == "win32":
    # aiodns (used by HA's shared session) does not work on Windows event loops.
    async def _threaded_resolve(self, host, port=0, family=socket.AF_INET):
        return await aiohttp.ThreadedResolver().resolve(host, port, family)

    aiohttp.resolver.AsyncResolver.resolve = _threaded_resolve

# Live tests against wbl.de need real sockets.
pytest_socket.disable_socket = lambda *a, **k: None
pytest_socket.socket_allow_hosts = lambda *a, **k: None
pytest_plugins = ["pytest_homeassistant_custom_component"]

# Import this repo's custom_components before the plugin's own testing_config
# package can claim the name, otherwise HA does not find wbl_luenen.
import custom_components  # noqa: E402,F401

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
