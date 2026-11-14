<?php
// Local package verification only; NEVER shipped.
declare(strict_types=1);
define('HITV_POSTBACK_ENTRY','postback');
require $argv[1].'/src/Receiver.php';require $argv[1].'/src/Kernel.php';
require $argv[1].'/src/BuildInfo.php';
use Hitv\{CpanelReceiver,OgAdsCallbackContract,OgAdsPeerVerifier,OfferError};
$passed=0;
function check(bool $ok,string $label):void{global $passed;if(!$ok)throw new RuntimeException($label);$passed++;echo "PASS $label\n";}
function server(string $path='/hitv-ogads/postback.php'):array{return ['REQUEST_METHOD'=>'GET','REQUEST_URI'=>$path,'SCRIPT_NAME'=>$path,'HTTP_HOST'=>'upxp.store','HTTPS'=>'on','REMOTE_ADDR'=>'198.51.100.7'];}
function run(array $s=[],string $query='',?array $config=null,string $entry='postback'):array{return CpanelReceiver::handle($s+server(),$query,$config??CpanelReceiver::defaults(),$entry);}
$dummy='offer_id=910001&aff_sub4='.str_repeat('0',32).'&ip=192.0.2.20';
[$code,$body]=run();check($code===503&&$body['error']==='OGADS_ACTIVATION_INCOMPLETE'&&!$body['conversionRecorded'],'empty callback stays disabled');
[$code,$body]=run([],$dummy);check($code===503&&!$body['conversionRecorded'],'plausible callback cannot record');
check(run([],str_replace('910001','910002',$dummy))[0]===503,'second offer cannot unlock');
check(run([],$dummy)[0]===503,'duplicate cannot credit');
check(run(['REQUEST_URI'=>'/hitv-ogads/api/v1/offers/ogads/postback'],$dummy)[0]===503,'exact REST alias shares closed endpoint');
[$code,$body]=run(server('/hitv-ogads/health.php'),'',null,'health');check($code===200&&$body['mode']==='disabled'&&!$body['conversionRecording']&&!$body['liveCampaigns'],'health honestly reports disabled');
check(run(['REQUEST_METHOD'=>'HEAD']+server('/hitv-ogads/health.php'),'',null,'health')[0]===200,'health HEAD allowed');
check(run(server('/hitv-ogads/health.php'),'anything=1',null,'health')[0]===400,'health rejects query data');
foreach(['POST','PUT','DELETE','OPTIONS','HEAD'] as $method)check(run(['REQUEST_METHOD'=>$method],$dummy)[0]===405,'callback rejects '.$method);
check(run(['HTTPS'=>'off'],$dummy)[0]===426,'HTTP denied');
check(run(['HTTPS'=>'off','HTTP_X_FORWARDED_PROTO'=>'https','HTTP_FORWARDED'=>'proto=https'],$dummy)[0]===426,'forwarded HTTPS cannot bypass transport');
foreach(['attacker.example','www.upxp.store','upxp.store:443','upxp.store.attacker.example'] as $host)check(run(['HTTP_HOST'=>$host],$dummy)[0]===403,'unexpected host denied '.$host);
foreach(['/hitv-ogads/','/postback.php','/hitv-ogads/postback.php/extra','/hitv-ogads/api/v1/offers/ogads/simulated-postback','/hitv-ogads/%70ostback.php'] as $path)check(run(['REQUEST_URI'=>$path],$dummy)[0]===404,'non-exact route denied '.$path);
check(run([],str_repeat('x',2049))[0]===414,'oversized query denied');
check(run([],"bad=%ZZ")[0]===503,'disabled callback does not process malformed data');
$config=CpanelReceiver::defaults();$config['live_enabled']=true;check(run([],$dummy,$config)[0]===503,'live flag cannot activate writer');
$config=CpanelReceiver::defaults();$config['confirmed_sender_ips']=['198.51.100.7'];check(run([],$dummy,$config)[0]===503,'configured sender cannot activate writer');
$config['api_token']='not-a-real-token';check(run([],$dummy,$config)[0]===503,'unexpected secret config is not accepted');
$config=CpanelReceiver::defaults();$config['confirmed_sender_ips']=['invalid'];check(run([],$dummy,$config)[0]===503,'invalid sender config fails closed');
check(run([],$dummy,[])[0]===503,'missing configuration fields fail closed');
$parsed=OgAdsCallbackContract::parse($dummy);check($parsed['aff_sub4']===str_repeat('0',32)&&$parsed['offer_id']==='910001','original contract parser retained');
foreach([$dummy.'&payout=0.01',str_replace('aff_sub4=','aff_sub=',$dummy),$dummy.'&offer_id=910002'] as $query){try{OgAdsCallbackContract::parse($query);check(false,'strict contract');}catch(OfferError $e){check($e->status===400,'unsupported or duplicate macro rejected');}}
$peer=new OgAdsPeerVerifier(['198.51.100.7'],'upxp.store');$peer->verify(server());check(true,'existing sender verifier accepts injected fixture');
try{$peer->verify(['REMOTE_ADDR'=>'192.0.2.21','HTTP_X_FORWARDED_FOR'=>'198.51.100.7','HTTP_X_REAL_IP'=>'198.51.100.7']+server());check(false,'peer spoof rejected');}catch(OfferError $e){check($e->status===403,'existing sender verifier rejects forged forwarding');}
check(CpanelReceiver::config($argv[1].'/absent-config.php')===CpanelReceiver::defaults(),'no configuration required for disabled deployment');
check(!class_exists('Hitv\OgAdsConversionLedger')&&!class_exists('Hitv\DemoOfferService')&&!class_exists('Hitv\OgAdsApiClient'),'storage simulation and outbound transport absent');
// Root, current cPanel subdirectory, and a nested canonical mount behave identically.
foreach(['','/hitv-ogads','/staging/receiver-2'] as $base){
    $health=server($base.'/health.php');$callback=server($base.'/postback.php');
    [$code,$body]=run($health,'',null,'health');
    check($code===200&&$body['mode']==='disabled'&&!$body['conversionRecording'],'health at mount '.($base?:'/'));
    check(run(['REQUEST_METHOD'=>'HEAD']+$health,'',null,'health')[0]===200,'health HEAD at mount '.($base?:'/'));
    check(run(['HTTPS'=>'off']+$health,'',null,'health')[0]===426,'root-aware routing does not bypass HTTPS '.$base);
    [$code,$body]=run($callback,$dummy);
    check($code===503&&$body['error']==='OGADS_ACTIVATION_INCOMPLETE'&&!$body['conversionRecorded'],'callback remains disabled at '.$base);
    check(run(['REQUEST_URI'=>$base.'/postback.php?'.$dummy]+$callback,$dummy)[0]===503,'query does not change callback route '.$base);
    check(run(['REQUEST_URI'=>$base.'/api/v1/offers/ogads/postback?'.$dummy]+$callback,$dummy)[0]===503,'exact rewritten alias at '.$base);
    check(run(['REQUEST_URI'=>$base.'/health.php?anything=1']+$health,'anything=1',null,'health')[0]===400,'health query guard at '.$base);
    check(run($health,$dummy)[0]===404,'health script cannot be callback '.$base);
    check(run($callback,'',null,'health')[0]===404,'callback script cannot be health '.$base);
}
foreach([
    '//hitv-ogads/postback.php','https://upxp.store/hitv-ogads/postback.php',
    '/hitv-ogads-other/postback.php','/hitv-ogads2/postback.php','/prefix/hitv-ogads/postback.php',
    '/hitv-ogads/../hitv-ogads/postback.php','/hitv-ogads/./postback.php',
    '/hitv-ogads/%2e%2e/postback.php','/hitv-ogads%2fpostback.php','/hitv-ogads//postback.php',
    '/hitv-ogads/postback.php/','/hitv-ogads/postback.php#fragment','/hitv-ogads/postback.php;anything',
    '/hitv-ogads/api/v1/offers/ogads/postback/extra',
] as $path)check(run(['REQUEST_URI'=>$path],$dummy)[0]===404,'ambiguous or mismatched path denied '.$path);
foreach(['','postback.php','/health.php','/hitv-ogads/postback.php/extra','/hitv-ogads//postback.php',
    '/hitv-ogads/../postback.php','/hitv-ogads/%70ostback.php','/hitv-ogads/api/v1/offers/ogads/postback'] as $script)
    check(run(['SCRIPT_NAME'=>$script],$dummy)[0]===404,'invalid or mismatched executing script denied '.$script);
check(run(['SCRIPT_NAME'=>null],$dummy)[0]===404,'missing script does not guess a mount');
check(run(['REQUEST_URI'=>null],$dummy)[0]===404,'missing request URI fails closed');
check(run(['PATH_INFO'=>'/extra'],$dummy)[0]===404,'PATH_INFO cannot smuggle a route');
check(run(['REQUEST_URI'=>'/unrelated','HTTP_X_ORIGINAL_URL'=>'/hitv-ogads/postback.php','HTTP_X_REWRITE_URL'=>'/hitv-ogads/postback.php'],$dummy)[0]===404,'forwarded URL headers cannot select route');
check(run(server('/hitv-ogads/postback.php'),$dummy,null,'unknown')[0]===404,'unknown entry fails closed');
$manifest=json_decode(file_get_contents($argv[1].'/package-manifest.json'),true,512,JSON_THROW_ON_ERROR);
[$status,$body]=run(server('/hitv-ogads/health.php'),'',null,'health');
check($body['build']===['version'=>$manifest['version'],'payloadSha256'=>$manifest['payloadSha256']],'health reports exact built identity');
check(!array_key_exists('build',run([],$dummy)[1]),'callback response contract unchanged');
echo json_encode(['passed'=>$passed,'failed'=>0,'conversionsRecorded'=>0,'externalRequests'=>0])."\n";
