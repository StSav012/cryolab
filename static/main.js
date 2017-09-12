var chart = AmCharts.makeChart("chartdiv", {
  "type": "serial",
  //"theme": "light",
  "marginRight": 40,
  "marginLeft": 40,
  "autoMarginOffset": 20,
  "mouseWheelZoomEnabled": true,
  "valueAxes": [{
    "id": "tA",
    "axisAlpha": 0,
    "position": "left",
    "ignoreAxisWidth": true,
    "precision": 2,
    "minPeriod": 0.01
  }],
  "balloon": {
    "borderThickness": 1,
    "shadowAlpha": 0
  },
  "graphs": [{
    "id": "tmpr_temperature",
    "balloon": {
      "drop": true,
      "animationDuration": 0
    },
    "bullet": "none",
    "bulletSize": 5,
    "hideBulletsCount": 50,
    "lineThickness": 2,
    "valueField": "value",
    "balloonText": "<span style='font-size:18px;'>[[value]] K</span>"
  }],
  "chartScrollbar": {
    "graph": "tmpr_temperature",
    "oppositeAxis": false,
    "offset": 30,
    "scrollbarHeight": 80,
    "backgroundAlpha": 0,
    "selectedBackgroundAlpha": 0.1,
    "selectedBackgroundColor": "#888888",
    "graphFillAlpha": 0,
    "graphLineAlpha": 0.5,
    "selectedGraphFillAlpha": 0,
    "selectedGraphLineAlpha": 1,
    "autoGridCount": true,
    "color": "#AAAAAA"
  },
  "chartCursor": {
    "pan": true,
    "valueLineEnabled": true,
    "valueLineBalloonEnabled": true,
    "cursorAlpha": 1,
    "cursorColor": "#258cbb",
    "limitToGraph": "tmpr_temperature",
    "valueLineAlpha": 0.2,
    "valueZoomable": true,
    "categoryBalloonDateFormat": "HH:NN:SS",
    "animationDuration": 0
  },
  "valueScrollbar": {
    "oppositeAxis": false,
    "offset": 64,
    "scrollbarHeight": 10
  },
  "categoryField": "time",
  "categoryAxis": {
    "parseDates": true,
//    "equalSpacing": true,
    "dashLength": 1,
    "minorGridEnabled": true,
    "autoGridCount": true,
    "minPeriod": "ss"
  },
  "export": {
    "enabled": true
  },
  "dataProvider": []
});
chart.isZoomed = false;
chart.ignoreZoomed = true;
chart.addListener("zoomed", function(event) {
    if (chart.ignoreZoomed) {
        chart.ignoreZoomed = false;
        return;
    }
    chart.isZoomed = !(event.startIndex == 0 && event.chart.dataProvider.length - 1 == event.endIndex);
    chart.zoomStart = event.startIndex;
    chart.zoomEnd = event.endIndex;
});

chart.addListener("dataUpdated", function(event) {
    if (!chart.isZoomed) {
        return;
    }
    chart.zoomToIndexes(event.chart.dataProvider.length - (chart.zoomEnd-chart.zoomStart+1), event.chart.dataProvider.length);
});
/******************************************************************************/
function update_values() {
    $SCRIPT_ROOT = {{ request.script_root|tojson|safe }};
    $.getJSON("json",
        function(data) {
            if (data.cmpr_pressures &&
                data.cmpr_pressures[0] != "None" &&
                data.cmpr_pressures[0] != "") {
                $("#pressure1").text(data.cmpr_pressures[0]);
            }
            else {
                $("#pressure1").html("<b>??</b>");
            }
            if (data.cmpr_temperatures &&
                data.cmpr_temperatures[0] != "None" &&
                data.cmpr_temperatures[0] != "") {
                for (var i = 0; i < 3; ++i) {
                    $("#temperature" + (i+1)).text(data.cmpr_temperatures[i]);
                }
            }
            else {
                for (var i = 0; i < 3; ++i) {
                    $("#temperature" + (i+1)).html("<b>??</b>");
                }
            }
            {% for id in ['cmpr_local_on',
                          'cmpr_cold_head_run',
                          'cmpr_cold_head_pause',
                          'cmpr_fault_off',
                          'cmpr_oil_fault_off',
                          'cmpr_solenoid_on',
                          'cmpr_pressure_off',
                          'cmpr_oil_level_alarm',
                          'cmpr_water_flow_alarm',
                          'cmpr_water_temperature_alarm',
                          'cmpr_helium_temperature_off',
                          'cmpr_mains_off',
                          'cmpr_motor_temperature_off',
                          'cmpr_system_on'] %}
                if (data.{{ id }} &&
                    data.{{ id }} != "None" &&
                    data.{{ id }} != "") {
                    $("#{{ id }}").addClass("on");
                    $("#{{ id }}").removeClass("off");
                }
                else {
                    $("#{{ id }}").addClass("off");
                    $("#{{ id }}").removeClass("on");
                }
            {% endfor %}
            if (data.tmpr_temperature &&
                data.tmpr_temperature != "None" &&
                data.tmpr_temperature != "") {
                $("#temperature").text(data.tmpr_temperature);
                chart.dataProvider.push({
                    time:  new Date(),
                    value: data.tmpr_temperature
                });
                chart.ignoreZoomed = true;
                chart.validateData();
            }
            else {
                $("#temperature").html("<b>??</b>");
            }
            $("#time").text(new Date().toLocaleTimeString());
        });
}
setInterval(update_values, 1000)

