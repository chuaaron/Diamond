import diamond.collector
import sys
import urllib2

if sys.version_info >= (2,5):
    import xml.etree.cElementTree as ElementTree
else:
    import cElementTree as ElementTree

class BindCollector(diamond.collector.Collector):
    def get_default_config(self):
        """
        Returns the default collector settings
        """
        return { 
            'host': 'localhost',
            'port': 8080,
            'path': 'bind', 
            # Available stats:
            # - resolver (Per-view resolver and cache statistics)
            # - server (Incoming requests and their answers)
            # - zonemgmt (Requests/responses related to zone management)
            # - sockets (Socket statistics)
            # - memory (Global memory usage)
            'publish': [
                'resolver',
                'server',
                'zonemgmt',
                'sockets',
                'memory',
            ],
            # By default we don't publish these special views
            'publish_view_bind': False,
            'publish_view_meta': False,
        }

    def clean_counter(self, name, value):
        value = self.derivative(name, value)
        if value < 0:
            value = 0
        self.publish(name, value)

    def collect(self):
        req = urllib2.urlopen('http://%s:%d/' % (self.config['host'], self.config['port']))
        tree = ElementTree.parse(req)

        if not tree:
            raise ValueError("Corrupt XML file, no statistics found")

        root = tree.find('bind/statistics')

        if 'resolver' in self.config['publish']:
            for view in root.findall('views/view'):
                name = view.find('name').text
                if name == '_bind' and not self.config['publish_view_bind']:
                    continue
                if name == '_meta' and not self.config['publish_view_meta']:
                    continue
                nzones = len(view.findall('zones/zone'))
                self.publish('view.%s.zones' % name, nzones)
                for counter in view.findall('rdtype'):
                    self.clean_counter(
                        'view.%s.query.%s' % (name, counter.find('name').text),
                        int(counter.find('counter').text)
                    )
                for counter in view.findall('resstat'):
                    self.clean_counter(
                        'view.%s.resstat.%s' % (name, counter.find('name').text),
                        int(counter.find('counter').text)
                    )
                for counter in view.findall('cache/rrset'):
                    self.clean_counter(
                        'view.%s.cache.%s' % (name, counter.find('name').text.replace('!', 'NOT_')),
                        int(counter.find('counter').text)
                    )

        if 'server' in self.config['publish']:
            for counter in root.findall('server/requests/opcode'):
                self.clean_counter(
                    'requests.%s' % counter.find('name').text,
                    int(counter.find('counter').text)
                )
            for counter in root.findall('server/queries-in/rdtype'):
                self.clean_counter(
                    'queries.%s' % counter.find('name').text,
                    int(counter.find('counter').text)
                )
            for counter in root.findall('server/nsstat'):
                self.clean_counter(
                    'nsstat.%s' % counter.find('name').text,
                    int(counter.find('counter').text)
                )

        if 'zonemgmt' in self.config['publish']:
            for counter in root.findall('server/zonestat'):
                self.clean_counter(
                    'zonestat.%s' % counter.find('name').text,
                    int(counter.find('counter').text)
                )

        if 'sockets' in self.config['publish']:
            for counter in root.findall('server/sockstat'):
                self.clean_counter(
                    'sockstat.%s' % counter.find('name').text,
                    int(counter.find('counter').text)
                )

        if 'memory' in self.config['publish']:
            for counter in root.find('memory/summary').getchildren():
                self.publish(
                    'memory.%s' % counter.tag,
                    int(counter.text)
                )

# For quick tests
if __name__ == '__main__':
    import configobj
    class Handler:
        def process(self, metric):
            print str(metric).strip()
    b = BindCollector(configobj.ConfigObj('/etc/diamond/diamond.conf'), [Handler()])
    b.config = b.get_default_config()
    b.collect()