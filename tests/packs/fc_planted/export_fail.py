def build(doc):
    """A feature with no shape: the build succeeds but the STEP export fails."""
    obj = doc.addObject("Part::Feature", "Empty")
    return obj
