from collections import deque

class URLFrontier:

    def __init__(self):
        self.queue = deque()
        self.visited = set()

    def add(self, url):
        if url not in self.visited:
            self.queue.append(url)

    def get(self):
        if self.queue:
            url = self.queue.popleft()
            self.visited.add(url)
            return url
        return None

    def size(self):
        return len(self.queue)
