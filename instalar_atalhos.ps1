param([switch]$IniciarComOPc)
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$shell = New-Object -ComObject WScript.Shell

function Criar-Atalho($pasta, $nome, $alvo, $argumentos, $icone, $estilo) {
    $atalho = $shell.CreateShortcut((Join-Path $pasta "$nome.lnk"))
    $atalho.TargetPath = $alvo
    $atalho.Arguments = $argumentos
    $atalho.WorkingDirectory = $dir
    $atalho.IconLocation = $icone
    $atalho.WindowStyle = $estilo
    $atalho.Description = $nome
    $atalho.Save()
}

$real = "Biblioteca Pré Universitário"
$teste = "Biblioteca Pré Universitário (TESTE)"
$pythonw = Join-Path $dir "venv\Scripts\pythonw.exe"
$exe = Join-Path $dir "Biblioteca.exe"
if (Test-Path $exe) { $alvoReal = $exe; $argsReal = "" } else { $alvoReal = $pythonw; $argsReal = '"' + (Join-Path $dir "programa.py") + '"' }

foreach ($pasta in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
    Criar-Atalho $pasta $real $alvoReal $argsReal (Join-Path $dir "icone.ico") 1
    Criar-Atalho $pasta $teste (Join-Path $dir "iniciar_teste.bat") "" (Join-Path $dir "icone_teste.ico") 7
}
if ($IniciarComOPc) {
    Criar-Atalho ([Environment]::GetFolderPath("Startup")) $real $alvoReal $argsReal (Join-Path $dir "icone.ico") 1
    Write-Host "A biblioteca vai abrir sozinha quando voce entrar no Windows."
}
Write-Host "Icones criados."
