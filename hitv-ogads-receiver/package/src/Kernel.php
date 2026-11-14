<?php
declare(strict_types=1);
namespace Hitv;
if(!defined('HITV_POSTBACK_ENTRY')){http_response_code(404);exit;}

/** Shared-host adapter only. No database, outbound provider client or conversion sink. */
final class CpanelReceiver {
    public static function defaults():array {
        return ['expected_host'=>'upxp.store','live_enabled'=>false,'confirmed_sender_ips'=>[]];
    }
    public static function config(string $path):array {
        if(!is_file($path))return self::defaults();
        // Operator-owned PHP config is outside this website, never a request-controlled path.
        ob_start();
        try{$value=require $path;}finally{ob_end_clean();}
        if(!is_array($value))throw new \RuntimeException('Invalid configuration');
        return $value;
    }
    public static function handle(array $server,string $query,array $config,string $entry):array {
        try{
            if(array_diff(array_keys($config),array_keys(self::defaults()))||array_diff(array_keys(self::defaults()),array_keys($config))
                ||!is_string($config['expected_host'])||!preg_match('/^[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9]+(?:[a-z0-9-]*[a-z0-9])?)+$/D',$config['expected_host'])
                ||!is_bool($config['live_enabled'])||!is_array($config['confirmed_sender_ips'])||!array_is_list($config['confirmed_sender_ips']))
                return self::error(503,'CONFIGURATION_INVALID');
            foreach($config['confirmed_sender_ips'] as $ip)if(!is_string($ip)||!filter_var($ip,FILTER_VALIDATE_IP))return self::error(503,'CONFIGURATION_INVALID');
            // This package cannot become live by editing a flag or adding a key/address.
            if($config['live_enabled']!==false)return self::error(503,'OGADS_ACTIVATION_INCOMPLETE');
            if(!self::matchesRoute($server,$entry))return self::error(404,'ROUTE_NOT_FOUND');
            $method=$server['REQUEST_METHOD']??'';
            if(!in_array($method,$entry==='health'?['GET','HEAD']:['GET'],true))return self::error(405,'METHOD_NOT_ALLOWED');
            if(($server['HTTP_HOST']??'')!==$config['expected_host'])return self::error(403,'CALLBACK_ORIGIN_REJECTED');
            if(!in_array(strtolower((string)($server['HTTPS']??'')),['on','1'],true))return self::error(426,'HTTPS_REQUIRED');
            if(strlen($query)>2048)return self::error(414,'QUERY_TOO_LONG');
            if($entry==='health'){
                if($query!=='')return self::error(400,'QUERY_NOT_ALLOWED');
                return [200,['success'=>true,'service'=>'HITV OGAds postback','mode'=>'disabled','liveCampaigns'=>false,'conversionRecording'=>false,'build'=>BuildInfo::metadata()]];
            }
            // Reuse the existing disabled receiver. Never supply a conversion closure here.
            [$status,$body]=(new OgAdsPostbackEndpoint())->handle($server,$query);
            return [$status,$body+['mode'=>'disabled','conversionRecorded'=>false]];
        }catch(\Throwable){return self::error(503,'POSTBACK_UNAVAILABLE');}
    }
    private static function matchesRoute(array $server,string $entry):bool {
        if(!in_array($entry,['health','postback'],true)||($server['PATH_INFO']??'')!=='')return false;
        $script=$server['SCRIPT_NAME']??null;
        $uri=$server['REQUEST_URI']??null;
        // SCRIPT_NAME identifies the executing entry point, including its URL mount.
        // Require a canonical script path; do not infer a base from request headers.
        if(!is_string($script)||!is_string($uri)
            ||!preg_match('~\A(?:/[A-Za-z0-9_-]+)*/'.$entry.'\.php\z~D',$script))return false;
        $base=substr($script,0,-strlen('/'.$entry.'.php'));
        $path=explode('?',$uri,2)[0];
        // Compare complete paths, not an unchecked substring/prefix or decoded URL.
        return $path===$script||($entry==='postback'&&$path===$base.'/api/v1/offers/ogads/postback');
    }
    public static function error(int $status,string $code):array {
        return [$status,['success'=>false,'error'=>$code,'mode'=>'disabled','conversionRecorded'=>false]];
    }
}
