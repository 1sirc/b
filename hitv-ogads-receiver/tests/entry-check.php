<?php
// Local CLI request fixture; not a TLS server or a deployment dependency.
declare(strict_types=1);
[$script,$package,$base,$entry,$method,$alias]=$argv;
$path=$base.'/'.$entry.'.php';
$_SERVER=['REQUEST_METHOD'=>$method,'REQUEST_URI'=>$alias==='alias'?$base.'/api/v1/offers/ogads/postback':$path,
    'SCRIPT_NAME'=>$path,'HTTPS'=>'on','HTTP_HOST'=>'upxp.store','REMOTE_ADDR'=>'192.0.2.7','QUERY_STRING'=>''];
ob_start();
require $package.'/'.$entry.'.php';
$output=ob_get_clean();
echo json_encode(['status'=>http_response_code(),'body'=>$output===''?null:json_decode($output,true,512,JSON_THROW_ON_ERROR),'outputBytes'=>strlen($output)],JSON_THROW_ON_ERROR);
