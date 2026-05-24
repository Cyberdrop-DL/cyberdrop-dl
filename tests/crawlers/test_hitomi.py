from cyberdrop_dl.crawlers import hitomi_la

GG_JS = """
'use strict';
gg = { m: function(g) {
var o = 0;
switch (g) {
case 2765:
case 87:
case 3336:
case 3881:
case 1536:
case 1759:
case 695:
o = 1; break;
}
return o;
},
s: function(h) { var m = /(..)(.)$/.exec(h); return parseInt(m[2]+m[1], 16).toString(10); },
b: '1779613201/'
};
"""


NOZOMI = b"\x00;\xd5\xd4\x00;\xb9k\x00;\x1eQ\x008\x98^\x007 \xb2\x006\xd4y\x003\xa6\x9e"


def test_decode_servers() -> None:
    servers = hitomi_la._decode_servers(GG_JS)
    assert servers.root == 1779613201
    assert len(servers) == 7
    assert servers[3881] == 1
    assert servers[-999999] == 0


def test_decode_nozomi() -> None:
    result = hitomi_la._decode_nozomi_resp(NOZOMI)
    assert result == (3921364, 3914091, 3874385, 3709022, 3612850, 3593337, 3384990)
