"""Small Win32 helper for driving/observing the psdto3d GUI during verification."""
import ctypes, time, sys
from ctypes import wintypes
from PIL import Image

u = ctypes.windll.user32
g = ctypes.windll.gdi32
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)


def _classname(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(ctypes.c_void_p(h), b, 256)
    return b.value


def _title(h):
    b = ctypes.create_unicode_buffer(1024)
    u.GetWindowTextW(ctypes.c_void_p(h), b, 1024)
    return b.value


def windows(pid):
    out = []
    def cb(h, l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(p))
        if p.value == pid:
            out.append((h, _classname(h), _title(h), bool(u.IsWindowVisible(ctypes.c_void_p(h)))))
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def children(h, depth=0, maxdepth=3):
    out = []
    kids = []
    def cb(hh, l):
        kids.append(hh)
        return True
    u.EnumChildWindows(ctypes.c_void_p(h), WNDENUMPROC(cb), 0)
    for k in kids:
        out.append((k, _classname(k), _title(k)))
        if depth < maxdepth:
            out.extend(children(k, depth + 1, maxdepth))
    return out


def capture(h, path):
    u.SetWindowPos(ctypes.c_void_p(h), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002)
    r = wintypes.RECT()
    u.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(ctypes.c_void_p(h))
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(ctypes.c_void_p(h), mdc, 2)
    class BIH(ctypes.Structure):
        _fields_ = [('biSize', wt_dword := wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]
    bi = BIH(); bi.biSize = ctypes.sizeof(bi); bi.biWidth = w; bi.biHeight = -hh
    bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    Image.frombuffer('RGBA', (w, hh), buf, 'raw', 'BGRA', 0, 1).convert('RGB').save(path)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(ctypes.c_void_p(h), hdc)
    return w, hh


def command(h, wid):
    u.PostMessageW(ctypes.c_void_p(h), 0x111, wintypes.WPARAM(wid), wintypes.LPARAM(0))


def set_text(h, text):
    u.SetWindowTextW(ctypes.c_void_p(h), text)


def click(h):
    u.SendMessageW(ctypes.c_void_p(h), 0x00F5, 0, 0)  # BM_CLICK


def type_keys(text, delay=0.02):
    """Type literal text through keybd_event, ASCII only."""
    VK = {' ': 0x20, '\\': 0xDC, '.': 0xBE, ':': 0xBA, '_': 0xBD, '-': 0xBD}
    for ch in text:
        if ch.isalpha() or ch.isdigit():
            vk = ord(ch.upper())
            code = u.VkKeyScanW(ord(ch)) & 0xFF
            shift = (u.VkKeyScanW(ord(ch)) >> 8) & 0xFF
            if shift & 1:
                u.keybd_event(0x10, 0, 0, 0)
            u.keybd_event(code, 0, 0, 0); u.keybd_event(code, 0, 2, 0)
            if shift & 1:
                u.keybd_event(0x10, 0, 2, 0)
        else:
            res = u.VkKeyScanW(ord(ch)) & 0xFF
            shift = (u.VkKeyScanW(ord(ch)) >> 8) & 0xFF
            if res == 0xFF:
                continue
            if shift & 1:
                u.keybd_event(0x10, 0, 0, 0)
            u.keybd_event(res, 0, 0, 0); u.keybd_event(res, 0, 2, 0)
            if shift & 1:
                u.keybd_event(0x10, 0, 2, 0)
        time.sleep(delay)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'ls':
        for w in windows(int(sys.argv[2])):
            print('hwnd=%d vis=%s class=%s title=%r' % (w[0], w[3], w[1], w[2]))
    elif cmd == 'kids':
        for c in children(int(sys.argv[2]), maxdepth=int(sys.argv[3]) if len(sys.argv) > 3 else 2):
            print('hwnd=%d class=%s text=%r' % c)
    elif cmd == 'cap':
        print(capture(int(sys.argv[2]), sys.argv[3]))
    elif cmd == 'cmd':
        command(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == 'set':
        set_text(int(sys.argv[2]), sys.argv[3])
    elif cmd == 'click':
        click(int(sys.argv[2]))
    elif cmd == 'type':
        type_keys(sys.argv[2])
    elif cmd == 'fg':
        u.SetForegroundWindow(ctypes.c_void_p(int(sys.argv[2])))
