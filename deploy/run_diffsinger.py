"""DiffSinger boundary.

Voice packages differ in dictionaries, phonemes, variance models and licences.
This runner validates configuration and deliberately refuses to guess a voice-specific
conversion. Set QINSCAPE_DIFFSINGER_RUNNER to a tested voice-package command or replace
this boundary with its documented CLI.
"""
import argparse,os,shlex,subprocess
p=argparse.ArgumentParser();p.add_argument('--midi',required=True);p.add_argument('--lyrics',required=True);p.add_argument('--voice',required=True);p.add_argument('--output',required=True);a=p.parse_args()
template=os.getenv('QINSCAPE_DIFFSINGER_RUNNER','')
if not template:raise SystemExit('No licensed DiffSinger voice runner configured. Set QINSCAPE_DIFFSINGER_RUNNER with {midi} {lyrics} {voice} {output}.')
cmd=template.format(midi=a.midi,lyrics=a.lyrics,voice=a.voice,output=a.output);subprocess.run(shlex.split(cmd),check=True)
