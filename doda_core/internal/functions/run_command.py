import pexpect
import json

def run_command(command):
    print(f'🫡 running command: {command}')
    output = ""
    try:
        child = pexpect.spawn(command, encoding='utf-8', timeout=15)
        # Wait for the command to complete
        child.expect(pexpect.EOF) 
        # Get the command output
        output = child.before.strip() 
    except pexpect.exceptions.TIMEOUT as e:
        print(f'💥 Timeout error: The command took too long to complete.')
        output = 'error: command timeout'
    except Exception as e:
        print(f'💥 Error: {str(e)}')
        output = f'error: {str(e)}'

    return json.dumps({"output": output})
