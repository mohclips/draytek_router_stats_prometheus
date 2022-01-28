#!/usr/bin/python3

#
# A python OpenMetrics / Prometheus server to grab data from a DrayTek router
#
# Uses 'expect' to gather data from the telnet port

# https://www.draytek.co.uk/support/guides/kb-dsl-status-more

# https://kitz.co.uk/adsl/linestats_errors.htm

from os import getenv

import http.server

from prometheus_client import start_http_server
from prometheus_client import Summary, Gauge
from prometheus_client.core import CounterMetricFamily, REGISTRY

import pexpect # expect
from ttp import ttp # templating

# https://prometheus.io/docs/concepts/metric_types/

CUSTOM_COUNTERS = {
    'ne_LOS': 'Loss Of Signal count',
    'ne_LOS': 'Loss Of Frame count',
    'ne_LPR': 'Loss Of Power count',
    'ne_LOM': 'Loss Of Margin count',
    'ne_NCD': 'No Cell Delineation failure count',
    'ne_LCD': 'Loss Of Cell Delineation failure count',
    'ne_CRC': 'Cyclic Redundancy Check error count, number of CRC 8 anomalies (number of incorrect CRC)',
    'ne_HECError': 'Header Error Check Error count, HEC anomalies in the ATM Data Path',

    'fe_LOS': 'Loss Of Signal count',
    'fe_LOF': 'Loss Of Frame count',
    'fe_LPR': 'Loss Of Power count',
    'fe_LOM': 'Loss Of Margin count',
    'fe_NCD': 'No Cell Delineation failure count',
    'fe_LCD': 'Loss Of Cell Delineation failure count',
    'fe_CRC': 'Cyclic Redundancy Check error count, number of CRC 8 anomalies (number of incorrect CRC)',
    'fe_HECError': 'Header Error Check Error count, HEC anomalies in the ATM Data Path',
    
}

LATENCY = Summary('server_latency_gather_router_data_seconds', 'Time to get stats from the router')

NE_FECS  = Gauge('router_ne_fecs','Forward Error Correction Seconds - Line far-end (FECS-LFE)')
NE_ES    = Gauge('router_ne_es','Errored Seconds - Line far-end (ES-LFE)')
NE_SES	 = Gauge('router_ne_ses','Severely Errored Seconds - Line far-end (SES-LFE)')
NE_LOSS  = Gauge('router_ne_loss','Loss Of Signal Seconds')
NE_UAS	 = Gauge('router_ne_uas','Un-Available Seconds - Line (UAS-L) & Unavailable Seconds - Line far-end (UAS-LFE)')

FE_FECS  = Gauge('router_fe_fecs','Forward Error Correction Seconds - Line far-end (FECS-LFE)')
FE_ES    = Gauge('router_fe_es','Errored Seconds - Line far-end (ES-LFE)')
FE_SES	 = Gauge('router_fe_ses','Severely Errored Seconds - Line far-end (SES-LFE)')
FE_LOSS  = Gauge('router_fe_loss','Loss Of Signal Seconds')
FE_UAS	 = Gauge('router_fe_uas','Un-Available Seconds - Line (UAS-L) & Unavailable Seconds - Line far-end (UAS-LFE)')

#TODO: add some info gauges for the static text 

ext_template = """
<group name="rs">
  ---------------------- ATU-R Info (hw: annex {{hw_annex}}, f/w: annex {{fw_annex}}) -----------
{{ ignore }} Near End                   Far End  Note
 Trellis          : {{ne_Trellis}} {{fe_Trellis}}
 Bitswap          : {{ne_Bitswap}} {{fe_Bitswap}}
 ReTxEnable       : {{ne_ReTxEnable}} {{fe_ReTxEnable}}
 VirtualNoise     : {{ne_VirtualNoise}} {{fe_VirtualNoise}}
 20BitSupport     : {{ne_20BitSupport}} {{fe_20BitSupport}}
 LatencyPath      : {{ne_LatencyPath}} {{fe_LatencyPath}}
 LOS              : {{ne_LOS}} {{fe_LOS}}
 LOF              : {{ne_LOF}} {{fe_LOF}}
 LPR              : {{ne_LPR}} {{fe_LPR}}
 LOM              : {{ne_LOM}} {{fe_LOM}}
 SosSuccess       : {{ne_SosSuccess}} {{fe_SosSuccess}}
 NCD              : {{ne_NCD}} {{fe_NCD}}
 LCD              : {{ne_LCD}} {{fe_LCD}}
 FECS             : {{ne_FECS}} {{fe_FECS}} (seconds)
 ES               : {{ne_ES}} {{fe_ES}} (seconds)
 SES              : {{ne_SES}} {{fe_SES}} (seconds)
 LOSS             : {{ne_LOSS}} {{fe_LOSS}} (seconds)
 UAS              : {{ne_UAS}} {{fe_UAS}} (seconds)
 HECError         : {{ne_HECError}} {{fe_HECError}}
 CRC              : {{ne_CRC}} {{fe_CRC}}
 INP              : {{ne_INP}} {{fe_INP}} (symbols)
 INTLVDelay       : {{ne_INTLVDelay}} {{fe_INTLVDelay}} (1/100 ms)
 NFEC             : {{ne_NFEC}} {{fe_NFEC}}
 RFEC             : {{ne_RFEC}} {{fe_RFEC}}
 LSYMB            : {{ne_LSYMB}} {{fe_LSYMB}}
 INTLVBLOCK       : {{ne_INTLVBLOCK}} {{fe_INTLVBLOCK}}
 AELEM            : {{ne_AELEM}} ----
</group>
"""

class RouterCollector(object):
#
# Prometheus stuff, called when ever the METRICS_PORT is opened
#
    @LATENCY.time() # measure who long this function takes to run
    def collect(self):

        print("Gathering router stats...")

        try:
            child = pexpect.spawn (config.TELNET_CMD + ' ' + config.IP, timeout=config.SPAWN_TIMEOUT)

            child.expect("Account:")

            child.send (config.USERNAME +"\r")
            child.expect ("Password: ")
            child.send (config.PASSWORD+"\r")
            child.expect ("DrayTek> ")
            
            child.send ("vdsl status more\r")
            child.expect ("DrayTek> ")
            ext_results = child.before
            child.send ("exit\r")

            ext_results=str(ext_results.replace(b'\r',b''),'ascii') # convert to ascii string for parsing
            #print(ext_results)

            parser = ttp(data=ext_results, template=ext_template, log_level='INFO')
            parser.parse() # extract the info

            # print result in JSON format
            #p_ext_results = parser.result(format='json')[0]
            #print(p_ext_results)

            om = parser.result(format='raw')[0][0]
            #print(om)

            # Load up the Prometheus custom counters
            for c in CUSTOM_COUNTERS:
                #print("{} | {} | {}".format(c, CUSTOM_COUNTERS[c], om['rs'][c]))
                yield CounterMetricFamily("router_" + c, CUSTOM_COUNTERS[c], om['rs'][c])
            
            # load up the standard gauges - everything that is returned in seconds
            NE_FECS.set(om['rs']['ne_FECS'])
            NE_ES.set(om['rs']['ne_ES'])
            NE_SES.set(om['rs']['ne_SES'])
            NE_LOSS.set(om['rs']['ne_LOSS'])
            NE_UAS.set(om['rs']['ne_UAS'])

            FE_FECS.set(om['rs']['fe_FECS'])
            FE_ES.set(om['rs']['fe_ES'])
            FE_SES.set(om['rs']['fe_SES'])
            FE_LOSS.set(om['rs']['fe_LOSS'])
            FE_UAS.set(om['rs']['fe_UAS'])

        except Exception as e:
            print("Error gathering stats:", e)
            return


class ServerHandler(http.server.BaseHTTPRequestHandler):
#
# Web Browser stuff
#
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Prometheus metrics available on port {} /metrics\n".format(config.METRICS_PORT).encode("utf-8")) # a byte string

class Config(object):

    def __init__(self):
    # read in environment variables

        self.IP=getenv('IP','192.168.0.1')
        self.USERNAME=getenv('USERNAME','admin')
        self.PASSWORD=getenv('PASSWORD','password')

        self.SERVER_PORT=int(getenv('SERVER_PORT', '8081'))
        self.METRICS_PORT=int(getenv('METRICS_PORT','8001'))

        self.TELNET_CMD=getenv('TELNET_CMD','/usr/bin/telnet') # where does telnet live?
        self.SPAWN_TIMEOUT=int(getenv('SPAWN_TIMEOUT',5))


if __name__ == "__main__":

    # read in config from Environment Variables
    config = Config()
    #print(config.IP,config.USERNAME,config.PASSWORD,config.SPAWN_TIMEOUT)

    # this is called everytime the /metrics URI is called
    REGISTRY.register(RouterCollector())

    # start metrics server
    start_http_server(config.METRICS_PORT)
    
    # start web server - keeps the app up and running
    server = http.server.HTTPServer(('', config.SERVER_PORT), ServerHandler)
    print("Prometheus metrics available on port "+str(config.METRICS_PORT)+" /metrics")
    print("HTTP server available on port "+str(config.SERVER_PORT))
    server.serve_forever()

