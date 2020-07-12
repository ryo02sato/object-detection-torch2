import torch
import torch.nn as nn
import torch.nn.functional as F


class VGG16(nn.Module):
    def __init__(self, num_classes, weights_path=None):
        # initialize
        super(VGG16, self).__init__()

        # feature extraction layer
        layers = []
        in_channels = 3
        cfg = [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M_P', 512, 512, 512, 'M', 512, 512, 512, 'M_P']
        for i, v in enumerate(cfg):
            if v == 'M':
                layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
            elif v == 'M_P':
                layers += [nn.MaxPool2d(kernel_size=2, stride=2, padding=1)]
            else:
                layers += [
                    nn.Conv2d(in_channels=in_channels, out_channels=v, kernel_size=3, padding=1),
                    nn.BatchNorm2d(v),
                    nn.ReLU(inplace=True)
                ]
                in_channels = v

        self.features = nn.Sequential(*layers)

        # classification layer
        self.classifier = nn.Sequential(
            nn.Linear(512 * 7 * 7, 4096),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(4096, 4096),
            nn.ReLU(inplace=True),
            nn.Dropout(),
            nn.Linear(4096, num_classes)
        )

        # load weights
        if weights_path:
            self.load_state_dict(torch.load(weights_path))
        else:
            self._initialize_weights()

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x

    def loss(self, output, target):
        output = F.softmax(output, dim=1)
        loss = nn.CrossEntropyLoss()(input=output, target=target)
        return loss

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(
                    m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.constant_(m.bias, 0)


class SSD(nn.Module):
    def __init__(self, num_classes, num_classes_vgg16, weights_path_ssd=None, weights_path_vgg16=None):
        # initialize
        super(SSD, self).__init__()
        self.num_classes = num_classes

        # extra feature layer
        layers = []
        in_channels = 512
        cfg = [(3, 1024), (1, 1024), (1, 256), (3, 512), (1, 128), (3, 256), (1, 128), (3, 256), (1, 128), (3, 256)]
        str_2_layers = {3, 5, 7, 9}
        for i, (k, v) in enumerate(cfg):
            s = 2 if i in str_2_layers else 1
            p = 1 if k == 3 and i < len(cfg) - 1 else 0
            layers += [
                nn.Conv2d(in_channels=in_channels, out_channels=v, kernel_size=k, stride=s, padding=p),
                nn.BatchNorm2d(v),
                nn.ReLU(inplace=True)
            ]
            in_channels = v

        vgg16 = VGG16(num_classes=num_classes_vgg16, weights_path=weights_path_vgg16)
        self.features = nn.Sequential(vgg16.features[:-1], *layers)

        self.classifier = {
            32: nn.Conv2d(in_channels=512, out_channels=4*(num_classes+4), kernel_size=3, padding=1),
            49: nn.Conv2d(in_channels=1024, out_channels=6*(num_classes+4), kernel_size=3, padding=1),
            55: nn.Conv2d(in_channels=512, out_channels=6*(num_classes+4), kernel_size=3, padding=1),
            61: nn.Conv2d(in_channels=256, out_channels=6*(num_classes+4), kernel_size=3, padding=1),
            67: nn.Conv2d(in_channels=256, out_channels=4*(num_classes+4), kernel_size=3, padding=1),
            73: nn.Conv2d(in_channels=256, out_channels=4*(num_classes+4), kernel_size=3, padding=1),
        }

    def forward(self, x):
        batch_size = x.size(0)
        y = torch.empty((batch_size, self.num_classes + 4, 0))

        for i, layer in enumerate(self.features):
            x = layer(x)
            if i in self.classifier:
                y = torch.cat([y, self.classifier[i](x).view(batch_size, self.num_classes + 4, -1)], dim=2)

        return y
