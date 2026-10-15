import json,os,pathlib,shutil,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class MandatoryLauncherTests(unittest.TestCase):
 def test_strict_assertion_is_forwarded_once_without_retry(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=pathlib.Path(temporary);(root/"scripts").mkdir();shutil.copy2(ROOT/"scripts/compiler.sh",root/"scripts/compiler.sh")
   source=root/"compiler";source.mkdir();(source/".gitignore").write_text("target/\n");(source/"tracked").write_text("fixture")
   def git(*args):return subprocess.check_output(["git","-C",str(source),*args],text=True).strip()
   git("init","-q");git("add",".");git("-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-qm","fixture")
   (root/"SOURCE_REF").write_text(git("rev-parse","HEAD"));(source/"target").mkdir();(source/"target/classpath.txt").write_text("fixture")
   marker=root/"argv.jsonl";java=root/"fake-java"
   java.write_text("#!"+sys.executable+"\nimport os,sys,json\nwith open(os.environ['ARGV_LOG'],'a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')\nraise SystemExit(2)\n");java.chmod(0o700)
   result=subprocess.run(["bash","scripts/compiler.sh","--core-io=off","file.ores"],cwd=root,env={**os.environ,"ORESLANG_SOURCE_DIR":str(source),"ORES_JAVA":str(java),"ARGV_LOG":str(marker)},capture_output=True,text=True)
   self.assertEqual(result.returncode,2,result.stderr)
   rows=marker.read_text().splitlines();self.assertEqual(len(rows),1,"must not retry without policy")
   args=json.loads(rows[0]);start=args.index("dev.oreslang.launcher.OresMain")
   self.assertEqual(args[start+1:],["--core-io=native-async-only","--core-io=off","file.ores"])
if __name__=="__main__":unittest.main()
