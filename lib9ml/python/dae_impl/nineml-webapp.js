function createHttpRequest()
{
    var xmlhttp;

    if (window.XMLHttpRequest)
    {// code for IE7+, Firefox, Chrome, Opera, Safari
        xmlhttp=new XMLHttpRequest();
    }
    else
    {// code for IE6, IE5
        xmlhttp=new ActiveXObject("Microsoft.XMLHTTP");
    }
    return xmlhttp;
}

function executeCommand(loadToTag, action, parameters, asynchronous)
{
    var xmlhttp = createHttpRequest();
    xmlhttp.onreadystatechange=function()
    {
        if (xmlhttp.readyState==4 && xmlhttp.status==200)
        {
            document.getElementById(loadToTag).innerHTML = xmlhttp.responseText;
        }
    }

    xmlhttp.open("POST", action, asynchronous);
    xmlhttp.setRequestHeader("Content-type","application/x-www-form-urlencoded");
    xmlhttp.send(parameters);
}
// "__NINEML_ACTION__=getAvailableALComponents"

