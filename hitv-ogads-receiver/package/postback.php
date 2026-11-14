<?php
declare(strict_types=1);
ini_set('display_errors','0');
ini_set('display_startup_errors','0');
ini_set('log_errors','0');
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header("Content-Security-Policy: default-src 'none'; frame-ancestors 'none'");
define('HITV_POSTBACK_ENTRY','postback');
$status=503;
$body=['success'=>false,'error'=>'POSTBACK_UNAVAILABLE','mode'=>'disabled','conversionRecorded'=>false];
if(PHP_VERSION_ID<80200){$body['error']='PHP_82_REQUIRED';}
else{
    set_error_handler(static function($severity,$message,$file,$line){throw new ErrorException('Receiver error',0,$severity,$file,$line);});
    ob_start();
    try{[$status,$body]=require __DIR__.'/src/bootstrap.php';}catch(Throwable $error){/* Never echo exceptions, configuration or request fields. */}
    finally{ob_end_clean();restore_error_handler();}
}
http_response_code($status);
if($status===405)header('Allow: '.(HITV_POSTBACK_ENTRY==='health'?'GET, HEAD':'GET'));
if(($_SERVER['REQUEST_METHOD']??'')!=='HEAD')echo json_encode($body,JSON_UNESCAPED_SLASHES);
