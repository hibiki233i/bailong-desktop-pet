"""Platform paths and optional macOS desktop integration."""
import os
import sys
from pathlib import Path

# Qt pays a lookup cost for every missing family, and the Windows fonts are absent on macOS.
UI_FONT='"PingFang SC","Helvetica Neue"' if sys.platform=='darwin' else '"Microsoft YaHei","Segoe UI"'

def resource_root():
    if not getattr(sys,'frozen',False):return Path(__file__).resolve().parents[1]
    executable=Path(sys.executable).resolve()
    return executable.parents[1]/'Resources' if sys.platform=='darwin' else executable.parent

def user_data():
    if os.environ.get('BAILONG_DATA_DIR'):return Path(os.environ['BAILONG_DATA_DIR'])
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/BailongPet'
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')/'BailongPet'

def state_root():
    return user_data() if sys.platform=='darwin' else resource_root()

def configure_mac_app():
    """Keep a source run out of the Dock, as LSUIElement does for the packaged app."""
    if sys.platform!='darwin':return
    try:
        from AppKit import NSApplication,NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except (ImportError,AttributeError):pass

def activate_mac_app():
    """An accessory app is never frontmost by itself, so a new window would open behind others."""
    if sys.platform!='darwin':return
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except (ImportError,AttributeError):pass
def on_mac_reopen(callback):
    """Opening a running .app sends it a reopen event; no second process starts. Keep the result alive."""
    if sys.platform!='darwin':return None
    try:
        import objc
        from Foundation import NSAppleEventManager,NSObject
        from PySide6.QtGui import QGuiApplication
    except ImportError:return None
    if QGuiApplication.platformName()!='cocoa':return None
    class ReopenHandler(NSObject):
        @objc.typedSelector(b'v@:@@')
        def handleReopen_reply_(self,event,reply):callback()
    handler=ReopenHandler.alloc().init()
    # Event class 'aevt' and id 'rapp' are kCoreEventClass and kAEReopenApplication.
    NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(handler,b'handleReopen:reply:',0x61657674,0x72617070)
    return handler
def configure_mac_window(widget):
    if sys.platform!='darwin':return
    try:
        import objc
        from AppKit import NSWindowCollectionBehaviorCanJoinAllSpaces,NSWindowCollectionBehaviorFullScreenAuxiliary,NSWindowCollectionBehaviorMoveToActiveSpace
        from PySide6.QtGui import QGuiApplication
    except ImportError:return
    # Only Cocoa's winId is an NSView pointer; dereferencing an offscreen id would crash.
    if QGuiApplication.platformName()!='cocoa':return
    try:
        view=objc.objc_object(c_void_p=int(widget.winId()))
        window=view.window()
        # Qt marks Tool windows MoveToActiveSpace, and AppKit raises if that meets CanJoinAllSpaces.
        behavior=window.collectionBehavior()&~NSWindowCollectionBehaviorMoveToActiveSpace
        window.setCollectionBehavior_(behavior|NSWindowCollectionBehaviorCanJoinAllSpaces|NSWindowCollectionBehaviorFullScreenAuxiliary)
    except (AttributeError,ValueError,objc.error):pass

def mac_fullscreen():
    try:
        import Quartz as q
        from AppKit import NSWorkspace
        front=NSWorkspace.sharedWorkspace().frontmostApplication()
        pid=front.processIdentifier()
        if pid==os.getpid():return False
        from desktop_visibility import covers_monitor
        displays=q.CGGetActiveDisplayList(32,None,None)[1]
        monitors=[]
        for display in displays:
            r=q.CGDisplayBounds(display);monitors.append((r.origin.x,r.origin.y,r.origin.x+r.size.width,r.origin.y+r.size.height))
        for w in q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly|q.kCGWindowListExcludeDesktopElements,q.kCGNullWindowID) or []:
            if w.get(q.kCGWindowOwnerPID)!=pid or w.get(q.kCGWindowLayer)!=0:continue
            b=w[q.kCGWindowBounds];r=(b['X'],b['Y'],b['X']+b['Width'],b['Y']+b['Height'])
            return any(covers_monitor(r,m) for m in monitors)
    except (ImportError,AttributeError,KeyError,TypeError):pass
    return False
