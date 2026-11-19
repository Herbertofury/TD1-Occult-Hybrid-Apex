"""Bounded recovery of a refused fixed loopback listener at game startup.

This policy submits no game commands. Explicit listener shutdown cancels it;
no successful command, client request or appearance edit is ever replayed.
"""


class StartupRetry:
    def __init__(self, interval=2.0, limit=5, window=15.0):
        self.interval, self.limit, self.window = interval, limit, window
        self.cancel()

    def cancel(self):
        self.next_due = None
        self.deadline = None
        self.attempts = 0

    def arm(self, now, error):
        self.cancel()
        # Windows may briefly refuse a port during a preceding process exit.
        # Other socket failures require diagnosis, not blind repeated startup.
        if error in (10013, 10048):
            self.next_due = now + self.interval
            self.deadline = now + self.window

    def take_due(self, now):
        if self.next_due is None:
            return False
        if now > self.deadline or self.attempts >= self.limit:
            self.next_due = None
            return False
        if now < self.next_due:
            return False
        self.attempts += 1
        self.next_due = now + self.interval
        return True
