class ChainLengthError(Exception):
    """Indicates the ProteinNet record's primary sequence
    and mask data did not appropriately map onto the PDB
    data as it should have. If this occurs, first suspect
    that the normalization procedure is removing too many
    residues. 
    See: https://github.com/aqlaboratory/proteinnet/issues/16
    """
    def __init__(self, got: int, expected: int):
        message = f'length of normalized chain ({got}) does not match masked primary sequence ({expected})'
        super(ChainLengthError, self).__init__(self, message)
        self.message = message
        self.got = got
        self.expected = expected
