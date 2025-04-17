import argparse

class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_action_invocation(self, action):
        if action.metavar == '\b':
            return ', '.join(action.option_strings)
        return super()._format_action_invocation(action)