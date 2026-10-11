#include "resblock_body.h"
#include "xil_cache.h"

static data_t* align_buffer(data_t* storage) {
    return reinterpret_cast<data_t*>((reinterpret_cast<UINTPTR>(storage) + 63U)
                                      & ~static_cast<UINTPTR>(63U));
}

Resblock_body::Resblock_body(int h, int w, int ch_in, int ch_out)
    : h(h), w(w), ch_in(ch_in), ch_out(ch_out) {
    Xil_AssertVoid(h > 0 && h == w && h % 2 == 0);
    Xil_AssertVoid(ch_in > 0 && ch_out > 0 && ch_out % 2 == 0);
    conv1 = new BasicConv(h, w, 3, 1, 1, ch_in, ch_out);
    conv2 = new BasicConv(h, w, 3, 1, 1, ch_out / 2, ch_out / 2);
    conv3 = new BasicConv(h, w, 3, 1, 1, ch_out / 2, ch_out / 2);
    conv4 = new BasicConv(h, w, 1, 1, 0, ch_out, ch_out);
    // Padding keeps hardware feature buffers separate from heap metadata.
    route_storage = new data_t[ch_out * h * w + 64];
    concat_storage = new data_t[ch_out * h * w + 64];
    route = align_buffer(route_storage);
    conv3_out = align_buffer(concat_storage);
}

Resblock_body::~Resblock_body() {
    delete conv1;
    delete conv2;
    delete conv3;
    delete conv4;
    delete[] route_storage;
    delete[] concat_storage;
}

void Resblock_body::forward(data_t* input, data_t* feat, data_t* out) {
    const int count = ch_out * h * w;
    const int half = count / 2;
    Xil_DCacheFlushRange((INTPTR)input, ch_in * h * w * sizeof(data_t));
    BasicConv* layers[] = {conv1, conv2, conv3, conv4};
    for (BasicConv* layer : layers) {
        Xil_DCacheFlushRange((INTPTR)layer->weight,
                            layer->ch_out * layer->ch_in * layer->k * layer->k * sizeof(data_t));
        Xil_DCacheFlushRange((INTPTR)layer->bias, layer->ch_out * sizeof(data_t));
    }
    Xil_DCacheFlushRange((INTPTR)route, count * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)conv3_out, count * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)feat, count * sizeof(data_t));
    Xil_DCacheFlushRange((INTPTR)out, (count / 2) * sizeof(data_t));

    conv1->forward(input, route);
    conv2->forward(route + half, conv3_out + half);
    conv3->forward(conv3_out + half, conv3_out);
    conv4->forward(conv3_out, feat);
    sampling(route, out, ch_out, h, 1);
    sampling(feat, out + count / 4, ch_out, h, 1);

    Xil_DCacheInvalidateRange((INTPTR)route, count * sizeof(data_t));
    Xil_DCacheInvalidateRange((INTPTR)conv3_out, count * sizeof(data_t));
    Xil_DCacheInvalidateRange((INTPTR)feat, count * sizeof(data_t));
    Xil_DCacheInvalidateRange((INTPTR)out, (count / 2) * sizeof(data_t));
}
