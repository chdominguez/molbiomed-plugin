"""
MolBioMed Plugin for Horus
"""

from Blocks.create_md_custom import custom_md_block
from Blocks.mm_pbsa import mm_pbsa_block
from HorusAPI import Plugin

plugin = Plugin()


plugin.addBlock(custom_md_block)
plugin.addBlock(mm_pbsa_block)
