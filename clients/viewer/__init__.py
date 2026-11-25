"""The viewer client: a safe workspace loader and a neutral STEP tessellator.

The package is the client side of the live viewer. It reads what the core
wrote and it never writes into a workspace. It imports the core; the core
never imports it.
"""
