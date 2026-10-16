import sys
result={k:getattr(v,'__file__',None) for k,v in sys.modules.items() if k.endswith('bifrost_wrinkles')}
