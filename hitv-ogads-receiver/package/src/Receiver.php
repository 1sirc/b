<?php
declare(strict_types=1);
namespace Hitv;
if(!defined('HITV_POSTBACK_ENTRY')){http_response_code(404);exit;}

final class OfferError extends \RuntimeException {
    public function __construct(public readonly int $status,public readonly string $codeName){parent::__construct($codeName);}
}

final class OgAdsCallbackContract {
    public const FORMAT_REFERENCE='https://github.com/learn-ogads/followers-landing-page/blob/version-1.0.0/README.md';
    public const AUTH_REFERENCE='https://github.com/learn-ogads/followers-landing-page/blob/version-1.0.0/api/postback.php';
    public static function readiness():array{return ['exampleFormatVerified'=>true,'exampleAuthentication'=>'connecting-source-IP-allowlist','currentAccountContractVerified'=>false,'currentSenderAddressesConfirmed'=>false,'providerTransactionIdVerified'=>false,'reversalContractVerified'=>false,'liveEnabled'=>false];}
    public static function parse(string $query):array {
        if($query===''||strlen($query)>2048||preg_match('/[\x00-\x20\x7f]/',$query)||preg_match('/%(?![a-fA-F0-9]{2})/',$query))throw new OfferError(400,'INVALID_CALLBACK');
        $v=[];
        foreach(explode('&',$query) as $pair){
            if(substr_count($pair,'=')!==1)throw new OfferError(400,'INVALID_CALLBACK');
            [$key,$value]=explode('=',$pair,2);$key=rawurldecode($key);$value=rawurldecode($value);
            if(!in_array($key,['offer_id','aff_sub4','ip'],true)||array_key_exists($key,$v))throw new OfferError(400,'INVALID_CALLBACK');
            $v[$key]=$value;
        }
        if(count($v)!==3||!preg_match('/^[1-9][0-9]{0,14}$/D',$v['offer_id']??'')||!preg_match('/^[a-f0-9]{32}$/D',$v['aff_sub4']??'')||!filter_var($v['ip']??'',FILTER_VALIDATE_IP))throw new OfferError(400,'INVALID_CALLBACK');
        $v['ip']=inet_ntop(inet_pton($v['ip']));return $v;
    }
}

final class OgAdsPeerVerifier {
    public function __construct(private readonly array $confirmedAddresses=[],private readonly string $expectedHost=''){}
    public function verify(array $server):void {
        if(!$this->confirmedAddresses||$this->expectedHost==='')throw new OfferError(503,'OGADS_SENDER_CONFIGURATION_REQUIRED');
        if(($server['REQUEST_METHOD']??'')!=='GET')throw new OfferError(405,'METHOD_NOT_ALLOWED');
        if(!in_array(strtolower((string)($server['HTTPS']??'')),['on','1'],true)||($server['HTTP_HOST']??'')!==$this->expectedHost)throw new OfferError(403,'CALLBACK_ORIGIN_REJECTED');
        $peer=$server['REMOTE_ADDR']??'';
        if(!filter_var($peer,FILTER_VALIDATE_IP))throw new OfferError(403,'CALLBACK_SENDER_REJECTED');
        foreach($this->confirmedAddresses as $ip)if(is_string($ip)&&filter_var($ip,FILTER_VALIDATE_IP)&&hash_equals(inet_pton($ip),inet_pton($peer)))return;
        // Never authenticate with query ip/session_ip, client headers, X-Forwarded-For or API Bearer.
        throw new OfferError(403,'CALLBACK_SENDER_REJECTED');
    }
}

final class OgAdsPostbackEndpoint {
    public function __construct(private readonly ?OgAdsPeerVerifier $sender=null,private readonly ?\Closure $acceptVerified=null){}
    public function handle(array $server,string $rawQuery):array {
        try{
            if($this->sender===null||$this->acceptVerified===null)throw new OfferError(503,'OGADS_ACTIVATION_INCOMPLETE');
            $this->sender->verify($server);
            $result=($this->acceptVerified)(OgAdsCallbackContract::parse($rawQuery));
            return [200,['success'=>true,'duplicate'=>$result['duplicate']??false]];
        }catch(OfferError $e){return [$e->status,['success'=>false,'error'=>$e->codeName]];}
        catch(\Throwable){return [503,['success'=>false,'error'=>'POSTBACK_UNAVAILABLE']];}
    }
}
