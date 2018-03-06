import logging
from logging.handlers import TimedRotatingFileHandler
from flask import Flask
from flask import render_template
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask import Response
import os
from IPy import IP
from subprocess import Popen, PIPE
import requests

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout
import configparser

import helium_compressor
import temperature_controller
import vacuum_pump
import pressure_gauge
import xmpp_bot
import tcp_emul
import redirector

def get_mac(ip):
    mac = None
    try:
        cmd = "arping -f -I wlan0 " + ip
        result = Popen(cmd, shell=True, stdout=PIPE)
        mac = result.stdout.readlines()[1].decode('ascii').split()[-2][1:-1]
        print(mac)
    except:
        pass
    return mac

config = configparser.ConfigParser()
config.read('/cryolab/python/wsgi.ini')

masters_list = [mac.split('#')[0].strip() for mac in config['masters']['MACs'].splitlines()]

cmpr = helium_compressor.worker()
tmpr = temperature_controller.worker()

pump = vacuum_pump.worker()
gauge = pressure_gauge.worker()

tmpr_rtm = temperature_controller.worker_rtm()

tcp_emul = tcp_emul.worker(temperature_controller = tmpr)

redirector = redirector.worker()

xmpp = xmpp_bot.bot(config['XMPP']['jid'], config['XMPP']['pass'])
# xmpp.register_plugin('xep_0030') # Service Discovery
# xmpp.register_plugin('xep_0004') # Data Forms
# xmpp.register_plugin('xep_0060') # PubSub
# xmpp.register_plugin('xep_0199') # XMPP Ping
                
xmpp.use_proxy = True
xmpp.proxy_config = {
    'host': config['proxy']['host'],
    'port': int(config['proxy']['port']),
    'username': config['proxy']['username'],
    'password': config['proxy']['password']
}

xmpp.trusted_senders = [login.split('#')[0].strip() for login in config['masters']['jabbers'].splitlines()]
xmpp.helium_compressor = cmpr
xmpp.temperature_controller = tmpr

print("Starting")

app = Flask(__name__)
app.url_map.strict_slashes = False
# app.debug = True
if not app.debug:
    formatter = logging.Formatter("[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
    handler = TimedRotatingFileHandler('/cryolab/python/logs/wsgi.log', when='midnight', interval=1, backupCount=5)
    handler.setLevel(logging.WARNING)
    handler.setFormatter(formatter)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    log.addHandler(handler)
    app.logger.addHandler(handler)
else:
    logging.basicConfig(level=logging.DEBUG)

if xmpp.connect((config['XMPP']['server'], int(config['XMPP']['port']))):
    print("XMPP connected")
else:
    print("XMPP connection failed")

xmpp.process(block=False)
cmpr.start()
tmpr.start()
tcp_emul.start()
tmpr_rtm.start()
pump.start()
#gauge.start()

@app.errorhandler(404)
def page_not_found(error):
    print('This route does not exist {}'.format(request.url))
    print(error)
    return 'This route does not exist {}'.format(request.url), 404

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/', methods=['GET', 'POST'])
def index():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('status.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           cmpr_pressures = cmpr.pressures,
                           cmpr_temperatures = cmpr.temperatures,
                           cmpr_config_mode = cmpr.config_mode,
                           cmpr_local_on = cmpr.local_on,
                           cmpr_cold_head_run = cmpr.cold_head_run,
                           cmpr_cold_head_pause = cmpr.cold_head_pause,
                           cmpr_fault_off = cmpr.fault_off,
                           cmpr_oil_fault_off = cmpr.oil_fault_off,
                           cmpr_solenoid_on = cmpr.solenoid_on,
                           cmpr_pressure_off = cmpr.pressure_off,
                           cmpr_oil_level_alarm = cmpr.oil_level_alarm,
                           cmpr_water_flow_alarm = cmpr.water_flow_alarm,
                           cmpr_water_temperature_alarm = cmpr.water_temperature_alarm,
                           cmpr_helium_temperature_off = cmpr.helium_temperature_off,
                           cmpr_mains_off = cmpr.mains_off,
                           cmpr_motor_temperature_off = cmpr.motor_temperature_off,
                           cmpr_system_on = cmpr.system_on,
                           tmpr_temperatures = tmpr.temperatures,
                           tmpr_output = tmpr.output)

@app.route('/json', methods= ['GET'])
def stuff():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return jsonify(cmpr_pressures = cmpr.pressures,
                   cmpr_temperatures = cmpr.temperatures,
                   cmpr_config_mode = cmpr.config_mode,
                   cmpr_local_on = cmpr.local_on,
                   cmpr_cold_head_run = cmpr.cold_head_run,
                   cmpr_cold_head_pause = cmpr.cold_head_pause,
                   cmpr_fault_off = cmpr.fault_off,
                   cmpr_oil_fault_off = cmpr.oil_fault_off,
                   cmpr_solenoid_on = cmpr.solenoid_on,
                   cmpr_pressure_off = cmpr.pressure_off,
                   cmpr_oil_level_alarm = cmpr.oil_level_alarm,
                   cmpr_water_flow_alarm = cmpr.water_flow_alarm,
                   cmpr_water_temperature_alarm = cmpr.water_temperature_alarm,
                   cmpr_helium_temperature_off = cmpr.helium_temperature_off,
                   cmpr_mains_off = cmpr.mains_off,
                   cmpr_motor_temperature_off = cmpr.motor_temperature_off,
                   cmpr_system_on = cmpr.system_on,
                   tmpr_temperatures = tmpr.temperatures,
                   tmpr_output = tmpr.output)

@app.route('/helium_compressor')
def cmpr_index():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('cmpr.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           pressures = cmpr.pressures,
                           temperatures = cmpr.temperatures,
                           config_mode = cmpr.config_mode,
                           local_on = cmpr.local_on,
                           cold_head_run = cmpr.cold_head_run,
                           cold_head_pause = cmpr.cold_head_pause,
                           fault_off = cmpr.fault_off,
                           oil_fault_off = cmpr.oil_fault_off,
                           solenoid_on = cmpr.solenoid_on,
                           pressure_off = cmpr.pressure_off,
                           oil_level_alarm = cmpr.oil_level_alarm,
                           water_flow_alarm = cmpr.water_flow_alarm,
                           water_temperature_alarm = cmpr.water_temperature_alarm,
                           helium_temperature_off = cmpr.helium_temperature_off,
                           mains_off = cmpr.mains_off,
                           motor_temperature_off = cmpr.motor_temperature_off,
                           system_on = cmpr.system_on)

@app.route('/helium_compressor/json', methods= ['GET'])
def cmpr_json():
    return jsonify(pressures = cmpr.pressures,
                   temperatures = cmpr.temperatures,
                   config_mode = cmpr.config_mode,
                   local_on = cmpr.local_on,
                   cold_head_run = cmpr.cold_head_run,
                   cold_head_pause = cmpr.cold_head_pause,
                   fault_off = cmpr.fault_off,
                   oil_fault_off = cmpr.oil_fault_off,
                   solenoid_on = cmpr.solenoid_on,
                   pressure_off = cmpr.pressure_off,
                   oil_level_alarm = cmpr.oil_level_alarm,
                   water_flow_alarm = cmpr.water_flow_alarm,
                   water_temperature_alarm = cmpr.water_temperature_alarm,
                   helium_temperature_off = cmpr.helium_temperature_off,
                   mains_off = cmpr.mains_off,
                   motor_temperature_off = cmpr.motor_temperature_off,
                   system_on = cmpr.system_on)

@app.route('/helium_compressor/do', methods = ['POST'])
def cmpr_do():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    mac = get_mac(request.remote_addr)
    if mac in masters_list:
        try:
            if cmpr.turn(request.json['action']):
                return "Command succeeded"
            else:
                logging.warning("compressor failed to process " + repr(request.json))
                return "Command failed"
        except:
            logging.error("an error occured while processing " + repr(request.json))
            return "Command failed with an error"
    logging.info("someone %s tried to manipulate the compressor", mac)
    return "Permission denied"

@app.route('/vacuum_pump')
def pump_index():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('pump.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           pumping_on = pump.is_on())

@app.route('/vacuum_pump/json', methods= ['GET'])
def pump_json():
    return jsonify(pumping_on = pump.pumping)

@app.route('/vacuum_pump/do', methods = ['POST'])
def pump_do():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    mac = get_mac(request.remote_addr)
    if mac in masters_list:
        try:
            if pump.turn(request.json['action']):
                return "Command succeeded"
            else:
                logging.warning("pump failed to process " + repr(request.json))
                return "Command failed"
        except:
            logging.error("an error occured while processing " + repr(request.json))
            return "Command failed with an error"
    logging.info("someone %s tried to manipulate the pump", mac)
    return "Permission denied"

@app.route('/temperature_controller')
def tmpr_index():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    return render_template('tmpr.html',
                           master_mind = (get_mac(request.remote_addr) in masters_list),
                           temperatures = tmpr.temperatures,
                           output = tmpr.output,
                           rtm  = temperature_controller.is_realtime_measurement_running)

@app.route('/temperature_controller/json', methods= ['GET'])
def tmpr_json():
    error = ""
    for index in range(2):
        if len(tmpr.error_in[index]) > 0:
            if len(error) > 0:
                error += '\n'
            error = tmpr.error_in[index]
        if len(tmpr.error_out[index]) > 0:
            if len(error) > 0:
                error += '\n'
            error += tmpr.error_out[index]
    pid_data = {1: {}, 2: {}}
    for output in [1, 2]:
        if 'mode' in tmpr.pid_data[output] and tmpr.pid_data[output]['mode'] != None:
            pid_data[output] = tmpr.pid_data[output]
        else:
            for item in ['input', 'mode', 'powerup_enable', 'range', 'value', 'P', 'I', 'D', 'manual']:
                pid_data[output][item] = None
    return jsonify(temperatures = tmpr.temperatures,
                   output = tmpr.output,
                   pid = pid_data,
                   error = error,
                   rtm = temperature_controller.is_realtime_measurement_running)

@app.route('/temperature_controller/temperature/A')
def tmpr_tmpr1():
    if tmpr.temperatures[0] != None:
        return repr(tmpr.temperatures[0])
    else:
        return repr(-1)

@app.route('/temperature_controller/temperature/B')
def tmpr_tmpr2():
    if tmpr.temperatures[1] != None:
        return repr(tmpr.temperatures[1])
    else:
        return repr(-1)

@app.route('/temperature_controller/pid/do', methods = ['POST'])
def tmpr_do():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    if get_mac(request.remote_addr) in masters_list:
        data = request.json;
        if tmpr.pid_turn(data):
            return "Command succeeded"
        else:
            return "Command failed"
    return "Permission denied"

@app.route('/jokes', methods = ['GET'])
def joke():
    if temperature_controller.is_realtime_measurement_running:
        return ""
    url = 'http://www.laughfactory.com/joke/loadmorejokes';
    try:
        r = requests.get(url, params=request.args, timeout=1)
        return r.text
    except:
        return '''{"jokes":[{"joke_text":"I'm not in the mood of joking :("}]}'''

@app.route('/temperature_controller/rtm', methods = ['POST'])
def rtm_tmpr():
    if temperature_controller.is_realtime_measurement_running:
        return "Please wait 'till a measurement is over"
    if get_mac(request.remote_addr) in masters_list:
        try:
            tmpr_rtm.label = request.json.get('label')
            tmpr_rtm.count = int(request.json.get('count'))
        except:
            tmpr_rtm.letter = ''
            tmpr_rtm.count = 0
            return "Measurement failed to start"
        else:
            tmpr_rtm.fire()
            return "Measurement started"
    return "Permission denied"

@app.route('/temperature_controller/rtm/json')
def rtm_tmpr_json():
    return jsonify(data = tmpr_rtm.res)

@app.route('/temperature_controller/rtm/csv')
def rtm_tmpr_csv():
#    print(csv(tmpr_rtm.res))
    return Response(csv(tmpr_rtm.res), mimetype="text/plain")

if __name__ == '__main__':
    print("Running")
#    app.config.update(APPLICATION_ROOT='/')
    try:
        redirector.start()
        app.run(host='0.0.0.0', port=80, threaded=True)
    except:
        redirector.stop()
        app.run(host='0.0.0.0', threaded=True)

