"use strict";

var jokes_perpage = 1;
var jokes_type = "category";
var url = 'jokes';

function loadJoke(selector){
    var offset = Math.round(50 * Math.random());
    var jokes_category = Math.round(50 * Math.random());
 	$.ajax({
        data : 'offset='+offset+'&joke_type='+jokes_type+'&jokes_perpage='+jokes_perpage+'&catid='+jokes_category,
        url  : url,
        type : "GET",
        success: function(response){
            var jokes = JSON.parse(response).jokes;
            if (jokes.length > 0) {
	        $(selector).first().text(jokes[0].joke_text);
                window.scrollTo(0, document.body.scrollHeight);
            }
            else {
                $(selector).first().text("");
            }
        }
    });
}

function setCookie(cname, cvalue, exdays) {
    var d = new Date();
    d.setTime(d.getTime() + (exdays*24*60*60*1000));
    var expires = "expires=" + d.toGMTString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
    var name = cname + "=";
    var decodedCookie = decodeURIComponent(document.cookie);
    var ca = decodedCookie.split(';');
    for (var i = 0; i < ca.length; ++i) {
        var c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

$(function() {
    var d = new Date()
    if (d.getDate() == 26 && d.getMonth() == 0 && getCookie("joke_of_the_day") != 1) {
        $(document.body).css({transform: "rotate(180deg)"});
        setCookie("joke_of_the_day", 1, 1);
    }
});

