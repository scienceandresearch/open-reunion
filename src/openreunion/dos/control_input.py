"""Panel press/release selection, separate from campaign and presentation timers."""


def released_slot(pressed, current, held):
    """Original 5643..5690: wait while held, cancel a changed release target."""
    if held:return None
    return pressed if current==pressed else 0


class PanelPress:
    """Track mouse buttons as one gesture; commit on the last release."""
    def __init__(self):
        self.buttons=set();self.target=None

    def cancel(self,*,reset=False):
        self.target=None
        if reset:self.buttons.clear()

    def press(self,button,slot,enabled):
        if button not in (1,2,3):return
        if not self.buttons:self.target=slot if enabled else None
        self.buttons.add(button)

    def release(self,button,slot,enabled):
        if button not in self.buttons:return 0
        self.buttons.remove(button)
        if not enabled:self.cancel()
        if self.target is None:return 0
        result=released_slot(self.target,slot,bool(self.buttons))
        if result is None:return 0
        self.cancel()
        return result
