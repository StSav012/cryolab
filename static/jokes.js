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
            }
            else {
                $(selector).first().text("");
            }
        }
    });
}

