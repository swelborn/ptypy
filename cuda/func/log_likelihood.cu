#include "log_likelihood.h"

#include "utils/Memory.h"
#include "utils/ScopedTimer.h"

#include <iostream>

/*************** Kernels **********************/

__global__ void calc_LLError_kernel(const unsigned char *mask,
                                    const float *LL,
                                    const float *Idata,
                                    const int *addr_info,
                                    float *LLError,
                                    int m,
                                    int n)
{
  // buffer to sum the matrices in shared memory
  extern __shared__ float sumbuffer[];

  int batch = blockIdx.x;
  int tx = threadIdx.x;
  int ty = threadIdx.y;
  int txy = tx * blockDim.y + ty;
  sumbuffer[txy] = 0.0f;

  auto da = addr_info + batch * 3 * 5 + 9;
  auto ma = da + 3;

  auto d_i0 = da[0];
  auto d_i1 = 0;
  auto d_i2 = 0;

  auto m_i0 = ma[0];
  auto m_i1 = 0;
  auto m_i2 = 0;

  // note: this only works for if N/M are divisible by 32
  for (int i = tx; i < m; i += blockDim.x)
  {
    for (int j = ty; j < n; j += blockDim.y)
    {
      auto LLidx = d_i0 * m * n + (d_i1 + i) * n + d_i2 + j;
      auto maskidx = m_i0 * m * n + (m_i1 + i) * n + m_i2 + j;

      auto vLL = LL[LLidx];
      auto vIdata = Idata[LLidx];
      auto vMask = mask[maskidx];
      auto m_by_LL_minus_Idata = vMask ? vLL - vIdata : 0.0f;
      auto vIdata_p_1 = vIdata + 1;
      auto sumval = (m_by_LL_minus_Idata * m_by_LL_minus_Idata) / vIdata_p_1;
      sumbuffer[txy] += sumval;
    }
  }

  // now add up sumbuffer in shared memory
  __syncthreads();
  int nt = blockDim.x * blockDim.y;
  int c = nt;
  while (c > 1)
  {
    int half = c / 2;
    if (txy < half)
    {
      sumbuffer[txy] += sumbuffer[c - txy - 1];
    }
    __syncthreads();
    c = c - half;
  }

  if (txy == 0)
  {
    LLError[batch] = sumbuffer[0] / float(n * m);
  }
}

/*************** Class implementation **********/

LogLikelihood::LogLikelihood(int i, int m, int n, int addr_i)
    : CudaFunction("log_likelihood"),
      i_(i),
      m_(m),
      n_(n),
      addr_i_(addr_i),
      ffprop_(i, m, n),
      abs2_(i * m * n),
      sum2buffer_(i, m, n, i, m, n, addr_i, addr_i)
{
  sum2buffer_.setAddrStride(5 * 3);
}

void LogLikelihood::setDeviceBuffers(complex<float> *d_probe_obj,
                                     unsigned char *d_mask,
                                     float *d_Idata,
                                     complex<float> *d_prefilter,
                                     complex<float> *d_postfilter,
                                     int *d_addr_info,
                                     float *d_out,
                                     int *d_outidx,
                                     int *d_startidx,
                                     int *d_indices,
                                     int outidx_size)
{
  d_probe_obj_ = d_probe_obj;
  d_mask_ = d_mask;
  d_Idata_ = d_Idata;
  d_prefilter_ = d_prefilter;
  d_postfilter_ = d_postfilter;
  d_addr_info_ = d_addr_info;
  d_out_ = d_out;
  d_outidx_ = d_outidx;
  d_startidx_ = d_startidx;
  d_indices_ = d_indices;
  outidx_size_ = outidx_size;
}

int LogLikelihood::calculateAddrIndices(const int *out1_addr)
{
  outidx_size_ = sum2buffer_.calculateAddrIndices(out1_addr);
  return outidx_size_;
}

void LogLikelihood::allocate()
{
  ScopedTimer t(this, "allocate (joint)");
  d_probe_obj_.allocate(i_ * m_ * n_);
  d_mask_.allocate(i_ * m_ * n_);
  d_Idata_.allocate(i_ * m_ * n_);
  d_prefilter_.allocate(m_ * n_);
  d_postfilter_.allocate(m_ * n_);
  d_addr_info_.allocate(addr_i_ * 5 * 3);
  d_out_.allocate(i_);
  d_LL_.allocate(i_ * m_ * n_);
  d_ft_.allocate(i_ * m_ * n_);

  ffprop_.setDeviceBuffers(
      d_probe_obj_.get(), d_ft_.get(), d_prefilter_.get(), d_postfilter_.get());
  ffprop_.allocate();

  abs2_.setDeviceBuffers(d_ft_.get(), d_LL_.get());
  abs2_.allocate();

  sum2buffer_.setDeviceBuffers(d_LL_.get(),
                               d_LL_.get(),  // in-place - ok here
                               d_addr_info_.get() + 6,
                               d_addr_info_.get() + 9,
                               d_outidx_,
                               d_startidx_,
                               d_indices_,
                               outidx_size_);
  sum2buffer_.allocate();
}

float *LogLikelihood::getOutput() const { return d_out_.get(); }

void LogLikelihood::transfer_in(const complex<float> *probe_obj,
                                const unsigned char *mask,
                                const float *Idata,
                                const complex<float> *prefilter,
                                const complex<float> *postfilter,
                                const int *addr_info)
{
  ScopedTimer t(this, "transfer in");
  gpu_memcpy_h2d(d_probe_obj_.get(), probe_obj, i_ * m_ * n_);
  gpu_memcpy_h2d(d_mask_.get(), mask, i_ * m_ * n_);
  gpu_memcpy_h2d(d_Idata_.get(), Idata, i_ * m_ * n_);
  gpu_memcpy_h2d(d_prefilter_.get(), prefilter, m_ * n_);
  gpu_memcpy_h2d(d_postfilter_.get(), postfilter, m_ * n_);
  // TODO: handle this case more explicitly 
  if (!d_addr_info_.isExternal())
  {
    gpu_memcpy_h2d(d_addr_info_.get(), addr_info, i_ * 5 * 3);
  }

  // transfer-in on sum_to_buffer needs to be called, for the internal
  // outidx buffers
  sum2buffer_.transfer_in(nullptr, nullptr, nullptr);
}

void LogLikelihood::transfer_out(float *out)
{
  ScopedTimer t(this, "transfer out");
  gpu_memcpy_d2h(out, d_out_.get(), i_);
}

void LogLikelihood::run()
{
  ScopedTimer t(this, "run");
  ffprop_.run(true, true, true);
  abs2_.run();
  sum2buffer_.run();

  dim3 threadsPerBlock = {32u, 32u, 1u};
  dim3 blocks = {unsigned(i_), 1u, 1u};
  calc_LLError_kernel<<<blocks,
                        threadsPerBlock,
                        threadsPerBlock.x * threadsPerBlock.y *
                            sizeof(float)>>>(d_mask_.get(),
                                             d_LL_.get(),
                                             d_Idata_.get(),
                                             d_addr_info_.get(),
                                             d_out_.get(),
                                             m_,
                                             n_);
  checkLaunchErrors();

  // sync device if timing is enabled
  timing_sync();
}

extern "C" void log_likelihood_c(const float *fprobe_obj,
                                 const unsigned char *mask,
                                 const float *fexit_wave,
                                 const float *Idata,
                                 const float *fprefilter,
                                 const float *fpostfilter,
                                 const int *addr_info,
                                 float *out,
                                 int i,
                                 int m,
                                 int n,
                                 int addr_i)
{
  auto probe_obj = reinterpret_cast<const complex<float> *>(fprobe_obj);
  auto prefilter = reinterpret_cast<const complex<float> *>(fprefilter);
  auto postfilter = reinterpret_cast<const complex<float> *>(fpostfilter);

  LogLikelihood ll(i, m, n, addr_i);
  ll.calculateAddrIndices(addr_info + 9);
  ll.allocate();
  ll.transfer_in(probe_obj, mask, Idata, prefilter, postfilter, addr_info);
  ll.run();
  ll.transfer_out(out);
}