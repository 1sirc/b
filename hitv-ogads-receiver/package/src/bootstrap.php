<?php
declare(strict_types=1);
if(!defined('HITV_POSTBACK_ENTRY')){http_response_code(404);exit;}
require __DIR__.'/Receiver.php';
require __DIR__.'/BuildInfo.php';
require __DIR__.'/Kernel.php';
// Deliberately outside /home/onekfuxn/upxp.store and never loaded from a request.
$privateConfig='/home/onekfuxn/hitv-private/ogads-postback.php';
$result=Hitv\CpanelReceiver::handle($_SERVER,$_SERVER['QUERY_STRING']??'',Hitv\CpanelReceiver::config($privateConfig),HITV_POSTBACK_ENTRY);
return $result;
