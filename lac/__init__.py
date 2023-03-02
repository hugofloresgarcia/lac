import audiotools

audiotools.ml.BaseModel.INTERN += ["lac.**"]
audiotools.ml.BaseModel.EXTERN += ["einops"]


from . import nn
from . import model

