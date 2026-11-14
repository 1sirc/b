<?php
// Operator CLI ONLY, keep outside every web document root. No application/config loading.
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
try{
    if($argc!==3||!preg_match('/\A[a-f0-9]{64}\z/',$argv[2]))throw new RuntimeException('INVALID_ARGUMENTS');
    $root=realpath($argv[1]);
    if($root===false||!is_dir($root)||is_link($argv[1]))throw new RuntimeException('DIRECTORY_REJECTED');
    $manifestPath=$root.'/package-manifest.json';
    if(is_link($manifestPath)||!is_file($manifestPath)||!hash_equals($argv[2],hash_file('sha256',$manifestPath)))
        throw new RuntimeException('MANIFEST_MISMATCH');
    $manifest=json_decode(file_get_contents($manifestPath),true,512,JSON_THROW_ON_ERROR);
    $expected=['.htaccess','.user.ini','README.md','health.php','postback.php','config/.htaccess',
        'config/receiver.example.php','src/.htaccess','src/Receiver.php','src/Kernel.php','src/bootstrap.php','src/BuildInfo.php'];
    $listed=array_keys($manifest['files']);sort($listed);sort($expected);
    if($listed!==$expected||$manifest['liveEnabled']!==false||$manifest['conversionWriterIncluded']!==false)
        throw new RuntimeException('MANIFEST_POLICY_REJECTED');
    $actual=[];
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root,FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::SELF_FIRST);
    foreach($iterator as $item){
        if($item->isLink())throw new RuntimeException('SYMLINK_REJECTED');
        if($item->isFile())$actual[]=str_replace('\\','/',substr($item->getPathname(),strlen($root)+1));
    }
    $expected[]='package-manifest.json';sort($actual);sort($expected);
    if($actual!==$expected)throw new RuntimeException('FILE_INVENTORY_MISMATCH');
    foreach($manifest['files'] as $name=>$digest)
        if(!hash_equals($digest,hash_file('sha256',$root.'/'.$name)))throw new RuntimeException('FILE_MISMATCH');
    echo json_encode(['verified'=>true,'version'=>$manifest['version'],'payloadSha256'=>$manifest['payloadSha256'],'files'=>count($actual)])."\n";
}catch(Throwable $e){
    // Never print filesystem paths, private config or file contents.
    echo json_encode(['verified'=>false,'error'=>'DEPLOYED_ARTIFACT_MISMATCH'])."\n";
    exit(1);
}
