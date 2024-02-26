import pexpect
import json

def run_command(command):
    print(f'🫡 running command: {command}')
    output = ""
    try: 
        # execute as bash command
        full_command = f"bash -c \"{command}\""
        child = pexpect.spawn(full_command, encoding='utf-8', timeout=15)
        child.expect(pexpect.EOF) 
        # get output/status of the command
        output = child.before.strip() 
        child.close()
        if child.exitstatus != 0:
            raise Exception(f'Command failed with exit code {child.exitstatus}')
        else:
            if output == "":
                output = "Command completed successfully!"
    except pexpect.exceptions.TIMEOUT as e:
        print(f'💥 Timeout error: The command took too long to complete.')
        output = 'error: command timeout'
    except Exception as e:
        print(f'💥 Error: {str(e)}')
        output = f'error: {str(e)}'

    return json.dumps({"output": output})